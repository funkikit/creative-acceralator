from __future__ import annotations

import json
import random
import uuid
from pathlib import Path
from typing import Dict, List, Tuple

import structlog

from app.models.schemas import VariationOut, VariationSeed, VariationTrace
from app.utils.llm_client import LLMClient


class VariationService:
    def __init__(self, llm_provider: str, prompt_dir: Path):
        self.llm = LLMClient(llm_provider)
        self.prompt_dir = prompt_dir
        self.log = structlog.get_logger(__name__).bind(service="variation")

    async def extract_variables(self, goal: str, constraints: List[str]) -> Dict:
        system = (self.prompt_dir / "system_extract.md").read_text(encoding="utf-8")
        payload = {"goal": goal, "constraints": constraints}
        user = json.dumps(payload, ensure_ascii=False)
        used_fallback = False
        try:
            text = await self.llm.complete(system, user)
            data = self._parse_llm_json(text)
            dynamic = data.get("dynamic_variables") or {}
            fixed = data.get("fixed_constraints") or []
            if not dynamic:
                dynamic = self._legacy_dynamic(data)
            if not fixed:
                fixed = self._legacy_constraints(data, constraints)
            dynamic = self._clean_dynamic(dynamic)
            fixed = self._clean_constraints(fixed + constraints)
            self.log.info(
                "variation_variables_extracted",
                goal=goal,
                dynamic_keys=list(dynamic.keys()),
                fixed_count=len(fixed),
                used_fallback=False,
            )
            return {
                "dynamic_variables": dynamic,
                "fixed_constraints": fixed,
                "used_fallback": False,
            }
        except Exception as exc:
            used_fallback = True
            self.log.warning(
                "variation_variables_fallback",
                goal=goal,
                error=str(exc),
                raw=locals().get("text", "")[:200],
            )
            # Dev fallback: provide deterministic variables when LLM is not available
            seed_dynamic = {
                "motif": ["sun", "beach", "waves"],
                "style": ["minimal", "flat", "retro"],
                "concept": ["summer", "festival", "music"],
                "palette": ["yellow/blue"],
            }
            if goal:
                goal_snippet = goal.split()[0]
                seed_dynamic.setdefault("concept", []).append(goal_snippet)
            fixed = self._clean_constraints(constraints)
            return {
                "dynamic_variables": seed_dynamic,
                "fixed_constraints": fixed,
                "used_fallback": used_fallback,
            }

    async def generate_variations(
        self,
        goal: str,
        dynamic_variables: Dict[str, List[str]],
        fixed_constraints: List[str],
        k: int,
        custom_variations: List[VariationSeed],
    ) -> List[VariationOut]:
        system = (self.prompt_dir / "system_variation.md").read_text(encoding="utf-8")
        cleaned_dynamic = {
            key: [v for v in values if v]
            for key, values in (dynamic_variables or {}).items()
            if isinstance(values, list)
        }
        if not cleaned_dynamic:
            cleaned_dynamic = {"concept": [goal] if goal else ["core idea"]}

        candidates: List[VariationOut] = []

        for _i in range(k):
            selection = {key: random.choice(values) if values else "" for key, values in cleaned_dynamic.items()}
            trace, prompt = await self._build_variation(system, goal, selection, fixed_constraints)
            candidates.append(
                VariationOut(
                    id=f"v_{uuid.uuid4().hex[:8]}",
                    prompt=prompt,
                    trace=trace,
                )
            )

        for seed in custom_variations:
            selection = self._seed_to_selection(seed)
            trace, prompt = await self._build_variation(system, goal, selection, fixed_constraints)
            candidates.append(
                VariationOut(
                    id=f"v_{uuid.uuid4().hex[:8]}",
                    prompt=prompt,
                    trace=trace,
                )
            )

        return candidates

    async def _build_variation(
        self,
        system_prompt: str,
        goal: str,
        selection: Dict[str, str],
        fixed_constraints: List[str],
    ) -> Tuple[VariationTrace, str]:
        trace = self._selection_to_trace(selection, fixed_constraints)
        payload = {
            "goal": goal,
            "selection": selection,
            "constraints": fixed_constraints,
            "trace": trace.model_dump(),
        }
        try:
            prompt = await self.llm.complete(system_prompt, json.dumps(payload, ensure_ascii=False))
        except Exception:
            prompt = self._fallback_prompt(goal, trace)
        return trace, prompt

    @staticmethod
    def _seed_to_selection(seed: VariationSeed) -> Dict[str, str]:
        base = {
            "motif": seed.motif or "",
            "style": seed.style or "",
            "concept": seed.concept or "",
            "palette": seed.palette or "",
            "target_audience": seed.target_audience or "",
            "brand_tone": seed.brand_tone or "",
        }
        extras = seed.extras or {}
        base.update({k: v for k, v in extras.items() if isinstance(v, str)})
        return base

    @staticmethod
    def _selection_to_trace(selection: Dict[str, str], fixed_constraints: List[str]) -> VariationTrace:
        known_keys = {"motif", "style", "concept", "palette", "target_audience", "brand_tone", "constraints"}
        extras = {k: v for k, v in selection.items() if k not in known_keys and v}
        dyn_constraints_raw = selection.get("constraints", "")
        dyn_constraints = []
        if isinstance(dyn_constraints_raw, str) and dyn_constraints_raw.strip():
            dyn_constraints = [seg.strip() for seg in dyn_constraints_raw.split(";") if seg.strip()]
        constraints = list(dict.fromkeys([*fixed_constraints, *dyn_constraints]))
        return VariationTrace(
            motif=selection.get("motif", ""),
            style=selection.get("style", ""),
            concept=selection.get("concept", ""),
            constraints=constraints,
            palette=selection.get("palette") or None,
            target_audience=selection.get("target_audience") or None,
            brand_tone=selection.get("brand_tone") or None,
            extras=extras,
        )

    @staticmethod
    def _fallback_prompt(goal: str, trace: VariationTrace) -> str:
        parts = [goal] if goal else []
        for label, value in (
            ("motif", trace.motif),
            ("style", trace.style),
            ("concept", trace.concept),
            ("palette", trace.palette),
            ("tone", trace.brand_tone),
        ):
            if value:
                parts.append(f"{label}:{value}")
        if trace.constraints:
            parts.append("constraints:" + ", ".join(trace.constraints))
        for k, v in trace.extras.items():
            parts.append(f"{k}:{v}")
        if not parts:
            return "Create a clean visual concept"
        return "Create " + ", ".join(parts)

    @staticmethod
    def _coerce_list(value) -> List[str]:
        if isinstance(value, list):
            return [str(v).strip() for v in value if str(v).strip()]
        if isinstance(value, str):
            return [seg.strip() for seg in value.replace("\n", ",").split(",") if seg.strip()]
        return []

    def _legacy_dynamic(self, data: Dict) -> Dict[str, List[str]]:
        dynamic: Dict[str, List[str]] = {}
        for key, value in data.items():
            if key in {"motif", "style", "concept", "palette", "target_audience", "brand_tone"}:
                values = self._coerce_list(value)
                if values:
                    dynamic[key] = values
        extras = data.get("dynamic") or {}
        if isinstance(extras, dict):
            for key, value in extras.items():
                values = self._coerce_list(value)
                if values:
                    dynamic[key] = values
        return dynamic

    def _legacy_constraints(self, data: Dict, fallback: List[str]) -> List[str]:
        candidates: List[str] = []
        if isinstance(data, list):
            candidates.extend(self._coerce_list(data))
        elif isinstance(data, str):
            candidates.extend(self._coerce_list(data))
        elif isinstance(data, dict):
            for key in ["constraints", "must_have", "rules", "fixed_constraints"]:
                if key not in data:
                    continue
                candidates.extend(self._coerce_list(data[key]))
        if not candidates:
            candidates.extend(fallback)
        return candidates

    def _clean_dynamic(self, dynamic: Dict[str, List[str]]) -> Dict[str, List[str]]:
        cleaned: Dict[str, List[str]] = {}
        for key, values in dynamic.items():
            normalized = [v for v in self._coerce_list(values) if v]
            if normalized:
                cleaned[str(key)] = normalized
        return cleaned

    def _clean_constraints(self, values: List[str]) -> List[str]:
        return list(dict.fromkeys(self._coerce_list(values)))

    @staticmethod
    def _strip_code_fence(text: str) -> str:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            # drop opening fence
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            # drop closing fence
            while lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            cleaned = "\n".join(lines).strip()
        return cleaned

    @classmethod
    def _parse_llm_json(cls, text: str) -> Dict:
        cleaned = cls._strip_code_fence(text or "")
        if not cleaned:
            raise ValueError("Empty LLM response")
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1:
            candidate = cleaned[start : end + 1]
        else:
            candidate = cleaned
        try:
            return json.loads(candidate)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Failed to parse LLM JSON: {exc}") from exc
