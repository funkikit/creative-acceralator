from pathlib import Path
import base64
import json
import os

from fastapi.testclient import TestClient

from app.main import app
from app.api import routes_variation
from app.utils.image_client import GeminiImageClient
from app.utils import storage


class DummyLLM:
    async def complete(self, system: str, user: str) -> str:
        try:
            payload = json.loads(user)
        except json.JSONDecodeError:
            payload = {}
        if isinstance(payload, dict) and payload.get("goal") and "selection" not in payload:
            return json.dumps(
                {
                    "dynamic_variables": {
                        "motif": ["kaiju"],
                        "style": ["cute"],
                        "concept": ["mascot"],
                    },
                    "fixed_constraints": payload.get("constraints", []) + ["no violence"],
                }
            )
        if isinstance(payload, dict) and payload.get("selection"):
            concept = payload["selection"].get("concept", "idea")
            return f"Cute {concept} corporate mascot, vivid colors"
        return "Cute kaiju corporate mascot, vivid colors"


def test_end_to_end_smoke(tmp_path: Path, monkeypatch):
    # ensure STATIC_DIR points to a writable temp
    static_dir = tmp_path / "static"
    static_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("STATIC_DIR", str(static_dir))

    # patch LLM used inside VariationService via dependency override
    def override_svc(req_llm: str = "gemini"):
        svc = routes_variation.VariationService(req_llm, Path("app/prompts"))
        svc.llm = DummyLLM()
        return svc

    app.dependency_overrides[routes_variation.svc] = override_svc

    # patch image client to write a tiny valid PNG
    async def fake_gen(self: GeminiImageClient, prompt: str) -> str:
        png_bytes = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMAASsJTYQAAAAASUVORK5CYII="
        )
        p = static_dir / "img_test.png"
        p.write_bytes(png_bytes)
        return str(p.resolve())

    monkeypatch.setattr(GeminiImageClient, "generate_png", fake_gen)

    client = TestClient(app)

    # 1) variations
    goal = "日本市場向けのカジュアルなキャラクターポスター"
    constraints = ["ロゴは右下", "文字はひらがなベース"]
    vars_resp = client.post(
        "/api/variations/variables",
        json={"goal": goal, "constraints": constraints, "llm": "gemini"},
    )
    assert vars_resp.status_code == 200
    var_data = vars_resp.json()
    assert var_data["used_fallback"] is False
    dynamic_variables = var_data["dynamic_variables"]

    variation_payload = {
        "goal": goal,
        "constraints": var_data["fixed_constraints"],
        "dynamic_variables": dynamic_variables,
        "k": 3,
        "llm": "gemini",
        "custom_variations": [
            {
                "motif": "hero",
                "style": "bold",
                "concept": "custom",
                "extras": {"notes": "user-added"},
            }
        ],
    }

    r = client.post("/api/variations", json=variation_payload)
    assert r.status_code == 200
    data = r.json()
    vids = [v["id"] for v in data["variations"]]
    assert len(vids) == 4

    # 2) images
    r2 = client.post("/api/images", json={"variation_ids": vids})
    assert r2.status_code == 200
    img_data = r2.json()["images"]
    assert len(img_data) == len(vids)
    assert all(i["url"].startswith("/static/") for i in img_data)

    # 3) validate (mock validation by overriding ValidationService would be heavier; here we skip calling it)
    # Instead, verify endpoint shape by monkeypatching ValidationService.run via dependency override
    from app.api import routes_validation
    from app.models.schemas import EvaluationOut, PersonaConfig, Scores

    async def fake_run(self, image_list, n_personas, personas_override=None):
        assert personas_override is not None
        assert personas_override[0].id == "p_payload"
        out = []
        for im in image_list:
            persona = PersonaConfig(
                id="p_payload",
                gender="F",
                age_band="20s",
                region="JP",
                background="tester",
                familiarity="high",
                summary="20s Female tester based in JP with high familiarity",
            )
            out.append(
                EvaluationOut(
                    persona_id="p_payload",
                    persona=persona,
                    image_id=im["id"],
                    scores=Scores(
                        Appeal=4.0,
                        BrandFit=4.1,
                        Originality=4.2,
                        Clarity=4.0,
                        CulturalSensitivity=4.3,
                        overall=4.12,
                    ),
                    comment="ok",
                    flags=[],
                )
            )
        return out

    monkeypatch.setattr(routes_validation.ValidationService, "run", fake_run)

    personas_payload = [
        {
            "id": "p_payload",
            "gender": "F",
            "age_band": "20s",
            "region": "JP",
            "background": "tester",
            "familiarity": "high",
            "summary": "20s Female tester based in JP with high familiarity",
        }
    ]

    r3 = client.post(
        "/api/validate",
        json={
            "image_ids": [i["id"] for i in img_data],
            "n_personas": 10,
            "llm": "openai",
            "personas": personas_payload,
        },
    )
    assert r3.status_code == 200
    evals = r3.json()["evaluations"]
    assert len(evals) == len(img_data)
    assert 0.0 <= evals[0]["scores"]["overall"] <= 5.0

    # 4) summary
    r4 = client.get("/api/summary?group_by=gender,age_band")
    assert r4.status_code == 200
    sm = r4.json()
    assert "overall" in sm and "ranking" in sm
