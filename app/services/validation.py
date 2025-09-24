from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.models.schemas import EvaluationOut, PersonaConfig, PersonaSpec, Scores
from app.utils.llm_client import LLMClient
from app.utils.sampler import build_persona_summary, sample_personas
import structlog


_BASE_PERSONA_KEYS = {"id", "gender", "age_band", "region", "background", "familiarity", "summary"}


def _safe(value: Any) -> str:
    return "" if value is None else str(value)


def _fallback_comment(persona: PersonaConfig, overall: float) -> str:
    role = persona.background or "担当者"
    audience_map = {
        "high": "コアなファン",
        "medium": "既存のお客様",
        "low": "初めての人",
    }
    audience = audience_map.get(str(persona.familiarity).lower(), "ターゲット")
    prefix = f"{role}として"
    if overall >= 0.85:
        msg = f"{prefix}素直にテンション上がる。{audience}にもこのまま出して良さそう。"
    elif overall >= 0.7:
        msg = f"{prefix}好印象。ただ{audience}向けにはコピーをもう少し鋭くしたい。"
    elif overall >= 0.5:
        msg = f"{prefix}まだ刺さりきらない。{audience}に伝わるようブランド感を強めてほしい。"
    else:
        msg = f"{prefix}正直ピンと来ていない。{audience}に響く別案を考え直したい。"
    return msg[:100]


def _ensure_summary(spec: PersonaSpec) -> str:
    base = spec.model_dump()
    if spec.summary:
        return spec.summary
    return build_persona_summary(base)


def _spec_to_config(spec: PersonaSpec) -> PersonaConfig:
    data = spec.model_dump()
    summary = _ensure_summary(spec)
    extras = {k: v for k, v in data.items() if k not in _BASE_PERSONA_KEYS}
    return PersonaConfig(
        id=spec.id,
        gender=spec.gender,
        age_band=spec.age_band,
        region=spec.region,
        background=spec.background,
        familiarity=spec.familiarity,
        summary=summary,
        extras=extras,
    )


def _dict_to_config(data: Dict) -> PersonaConfig:
    base = {key: data.get(key) for key in _BASE_PERSONA_KEYS}
    if not base.get("summary"):
        base["summary"] = build_persona_summary(base)
    extras_field = data.get("extras") or {}
    direct_extras = {k: v for k, v in data.items() if k not in _BASE_PERSONA_KEYS.union({"extras"})}
    merged_extras = {}
    merged_extras.update(extras_field)
    merged_extras.update({k: v for k, v in direct_extras.items() if k not in merged_extras})
    if not base.get("id"):
        raise ValueError("Persona missing required id")
    return PersonaConfig(
        id=_safe(base["id"]),
        gender=_safe(base["gender"]),
        age_band=_safe(base["age_band"]),
        region=_safe(base["region"]),
        background=_safe(base["background"]),
        familiarity=_safe(base["familiarity"]),
        summary=_safe(base["summary"]),
        extras=merged_extras,
    )


class ValidationService:
    def __init__(self, llm_provider: str, prompt_dir: Path, seed_csv: str):
        self.llm = LLMClient(llm_provider)
        self.prompt_dir = prompt_dir
        self.seed_csv = seed_csv
        self.log = structlog.get_logger(__name__).bind(service="validation")

    @staticmethod
    def from_specs(specs: List[PersonaSpec]) -> List[PersonaConfig]:
        return [_spec_to_config(spec) for spec in specs]

    async def _validate_one(self, persona: PersonaConfig, image_meta: Dict) -> EvaluationOut:
        system = (self.prompt_dir / "system_validator.md").read_text(encoding="utf-8")
        rubric = (self.prompt_dir / "rubric.json").read_text(encoding="utf-8")
        persona_payload = persona.model_dump()
        extras = persona_payload.pop("extras", {})
        if extras:
            persona_payload["extras"] = extras
        user = json.dumps(
            {"persona": persona_payload, "image": image_meta, "rubric": json.loads(rubric)},
            ensure_ascii=False,
        )
        try:
            text = await self.llm.complete(system, user)
            data = self._parse_llm_json(text)
            sc = data["scores"]
            return EvaluationOut(
                persona_id=persona.id,
                persona=persona,
                image_id=image_meta["id"],
                scores=Scores(**sc),
                comment=data.get("comment", ""),
                flags=data.get("flags", []),
                metadata=self._metadata(False),
            )
        except Exception as exc:
            self.log.warning(
                "validation_fallback",
                persona_id=persona.id,
                image_id=image_meta["id"],
                error=str(exc),
                raw=str(locals().get("text", ""))[:200],
            )
            # Dev fallback: produce plausible scores without external LLM
            def clamp(x: float) -> float:
                return max(0.0, min(1.0, round(x, 3)))

            base = 0.75
            adj = (hash(persona.id) ^ hash(image_meta["id"])) % 20 / 100.0 - 0.1
            Appeal = clamp(base + adj)
            BrandFit = clamp(base - adj / 2)
            Originality = clamp(base + adj / 3)
            Clarity = clamp(base + adj / 4)
            CulturalSensitivity = clamp(base - adj / 5)
            overall = clamp((Appeal + BrandFit + Originality + Clarity + CulturalSensitivity) / 5)
            persona_profile = persona
            comment = _fallback_comment(persona_profile, overall)
            return EvaluationOut(
                persona_id=persona_profile.id,
                persona=persona_profile,
                image_id=image_meta["id"],
                scores=Scores(
                    Appeal=Appeal,
                    BrandFit=BrandFit,
                    Originality=Originality,
                    Clarity=Clarity,
                    CulturalSensitivity=CulturalSensitivity,
                    overall=overall,
                ),
                comment=comment,
                flags=[],
                metadata=self._metadata(True),
            )

    def _metadata(self, used_fallback: bool) -> Dict[str, str]:
        model = ""
        provider = getattr(self.llm, "provider", "unknown")
        if provider == "openai":
            model = getattr(self.llm, "_openai_model", "")
        elif provider == "gemini":
            model = getattr(self.llm, "_gemini_model", "")
        return {
            "used_fallback": used_fallback,
            "llm_provider": provider,
            "llm_model": model,
        }

    @staticmethod
    def _strip_code_fence(text: str) -> str:
        cleaned = (text or "").strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            while lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            cleaned = "\n".join(lines).strip()
        return cleaned

    @classmethod
    def _parse_llm_json(cls, payload: str) -> Dict[str, Any]:
        cleaned = cls._strip_code_fence(payload)
        if not cleaned:
            raise ValueError("Empty LLM response")
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        candidate = cleaned[start : end + 1] if start != -1 and end != -1 else cleaned
        try:
            return json.loads(candidate)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Failed to parse evaluation JSON: {exc}") from exc

    async def run(
        self,
        image_list: List[Dict],
        n_personas: int,
        personas_override: Optional[List[PersonaConfig]] = None,
    ) -> List[EvaluationOut]:
        if personas_override:
            personas = personas_override
        else:
            personas_raw = sample_personas(n_personas, self.seed_csv)
            personas = [_dict_to_config(p) for p in personas_raw]
        results: List[EvaluationOut] = []
        for img in image_list:
            for p in personas:
                r = await self._validate_one(p, img)
                results.append(r)
        return results
