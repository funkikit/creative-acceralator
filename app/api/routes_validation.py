from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

from fastapi import APIRouter

from app.api.state import state
from app.models.schemas import (
    ValidateRequest,
    ValidateResponse,
    EvaluationOut,
    PersonaConfig,
    ValidationProgress,
)
from app.services.validation import ValidationService


router = APIRouter(prefix="/api/validate", tags=["validate"])

@router.post("", response_model=ValidateResponse)
async def validate(req: ValidateRequest):
    service = ValidationService(req.llm, Path("app/prompts"), "app/data/personas_seed.csv")
    # minimal image meta for persona validators
    images_meta: List[Dict] = []
    for iid in req.image_ids:
        meta = state.images.get(iid)
        if meta:
            images_meta.append(meta)
    personas_override: Optional[List[PersonaConfig]] = None
    if req.personas:
        personas_override = service.from_specs(req.personas)
    state.validation_progress = {
        "status": "initializing",
        "total": len(images_meta) * (len(personas_override) if personas_override else req.n_personas),
        "completed": 0,
        "message": None,
    }
    try:
        evals: List[EvaluationOut] = await service.run(images_meta, req.n_personas, personas_override)
    except Exception as exc:
        state.validation_progress = {
            "status": "error",
            "total": state.validation_progress.get("total", 0),
            "completed": state.validation_progress.get("completed", 0),
            "message": str(exc),
        }
        raise
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


@router.get("/progress", response_model=ValidationProgress)
async def validation_progress() -> ValidationProgress:
    data = state.validation_progress or {}
    return ValidationProgress(**data)


def _persona_group(persona: PersonaConfig) -> Dict[str, str]:
    data = persona.model_dump()
    extras = data.pop("extras", {}) or {}
    data.pop("summary", None)
    if isinstance(extras, dict):
        for k, v in extras.items():
            data[k] = v
    return data
