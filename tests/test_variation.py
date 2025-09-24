import asyncio
import json
from pathlib import Path

from app.services.variation import VariationService


class DummyLLM:
    async def complete(self, system: str, user: str) -> str:
        payload = json.loads(user)
        if "selection" not in payload:
            return json.dumps(
                {
                    "dynamic_variables": {
                        "motif": ["kaiju", "robot"],
                        "style": ["cute", "corporate"],
                        "concept": ["mascot"],
                    },
                    "fixed_constraints": payload.get("constraints", []) + ["no violence", "no sexual content"],
                }
            )
        selection = payload["selection"]
        return f"Prompt: {selection.get('motif','')} in {selection.get('style','')} style, concept {selection.get('concept','')}"


async def _run():
    svc = VariationService("gemini", Path("app/prompts"))
    # monkeypatch LLM
    svc.llm = DummyLLM()
    result = await svc.extract_variables("日本企業の怪獣マスコット", ["ロゴは左上"])
    assert result["used_fallback"] is False
    dynamic = result["dynamic_variables"]
    constraints = result["fixed_constraints"]
    outs = await svc.generate_variations("日本企業の怪獣マスコット", dynamic, constraints, 5, [])
    assert len(outs) == 5
    assert all(o.prompt and o.id.startswith("v_") for o in outs)


def test_variation_service():
    asyncio.run(_run())
