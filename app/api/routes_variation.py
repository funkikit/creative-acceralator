from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends

from app.api.state import state
from app.models.schemas import (
    VariationVariablesRequest,
    VariationVariablesResponse,
    VariationsRequest,
    VariationsResponse,
)
from app.services.variation import VariationService


router = APIRouter(prefix="/api/variations", tags=["variations"])


def svc(req_llm: str = "gemini"):
    return VariationService(req_llm, Path("app/prompts"))


@router.post("/variables", response_model=VariationVariablesResponse)
async def extract_variation_variables(
    req: VariationVariablesRequest, s: VariationService = Depends(svc)
):
    data = await s.extract_variables(req.goal, req.constraints)
    dynamic = data.get("dynamic_variables", {})
    fixed = data.get("fixed_constraints", [])
    return VariationVariablesResponse(
        goal=req.goal,
        llm=req.llm,
        dynamic_variables=dynamic,
        fixed_constraints=fixed,
        used_fallback=data.get("used_fallback", False),
    )


@router.post("", response_model=VariationsResponse)
async def create_variations(req: VariationsRequest, s: VariationService = Depends(svc)):
    custom = req.custom_variations or []
    variations = await s.generate_variations(
        goal=req.goal,
        dynamic_variables=req.dynamic_variables,
        fixed_constraints=req.constraints,
        k=req.k,
        custom_variations=custom,
    )
    prompt_run_id = f"pr_{uuid.uuid4().hex[:8]}"
    # cache for next steps
    for v in variations:
        state.variations[v.id] = {"prompt": v.prompt, "trace": v.trace.model_dump()}
    return VariationsResponse(prompt_run_id=prompt_run_id, variations=variations)
