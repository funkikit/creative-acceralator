from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends

from app.api.state import state
from app.models.schemas import ValidateRequest, ValidateResponse, EvaluationOut, PersonaConfig
from app.services.validation import ValidationService


router = APIRouter(prefix="/api/validate", tags=["validate"])


def svc(req_llm: str = "openai"):
    return ValidationService(req_llm, Path("app/prompts"), "app/data/personas_seed.csv")


@router.post("", response_model=ValidateResponse)
async def validate(req: ValidateRequest, s: ValidationService = Depends(svc)):
    # minimal image meta for persona validators
    images_meta: List[Dict] = []
    for iid in req.image_ids:
        meta = state.images.get(iid)
        if meta:
            images_meta.append(meta)
    personas_override: Optional[List[PersonaConfig]] = None
    if req.personas:
        personas_override = s.from_specs(req.personas)
    evals: List[EvaluationOut] = await s.run(images_meta, req.n_personas, personas_override)
    # cache for summary and return
    state.evaluations = [e.model_dump() for e in evals]
    # Attach persona attributes so summary endpoints can group by them later
    state.evals_for_summary = [
        {
            **e.model_dump(),
            "group": _persona_group(e.persona),
        }
        for e in evals
    ]
    return ValidateResponse(evaluations=evals)


def _persona_group(persona: PersonaConfig) -> Dict[str, str]:
    data = persona.model_dump()
    extras = data.pop("extras", {}) or {}
    data.pop("summary", None)
    if isinstance(extras, dict):
        for k, v in extras.items():
            data[k] = v
    return data
