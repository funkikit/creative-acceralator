import asyncio
import json
from pathlib import Path

from app.models.schemas import PersonaSpec
from app.services.validation import ValidationService


class DummyLLM:
    async def complete(self, system: str, user: str) -> str:
        payload = json.loads(user)
        # simple deterministic score by hashing ids
        base = sum(ord(c) for c in payload["persona"]["id"] + payload["image"]["id"]) % 50 / 10
        sc = {
            "Appeal": float(min(5.0, 1.0 + base)),
            "BrandFit": float(min(5.0, 1.2 + base)),
            "Originality": float(min(5.0, 0.8 + base)),
            "Clarity": float(min(5.0, 1.1 + base)),
            "CulturalSensitivity": float(min(5.0, 1.0 + base)),
        }
        overall = sum(sc.values()) / 5.0
        return json.dumps({"scores": {**sc, "overall": overall}, "comment": "ok", "flags": []})


async def _run():
    svc = ValidationService("openai", Path("app/prompts"), "app/data/personas_seed.csv")
    svc.llm = DummyLLM()
    images = [{"id": "img_001"}, {"id": "img_002"}]
    res = await svc.run(images, 10)
    assert len(res) == 20
    for e in res:
        assert 0.0 <= e.scores.overall <= 5.0
        assert e.persona_id == e.persona.id
        assert e.persona.summary
        assert len(e.comment) > 0

    spec = PersonaSpec(
        id="p_custom",
        gender="F",
        age_band="30s",
        region="JP",
        background="marketing lead",
        familiarity="high",
        summary="30s Female marketing lead based in JP with high familiarity",
    )
    custom_personas = ValidationService.from_specs([spec])
    override_res = await svc.run([{"id": "img_special"}], 1, custom_personas)
    assert len(override_res) == 1
    assert override_res[0].persona_id == "p_custom"


def test_validation_service():
    asyncio.run(_run())
