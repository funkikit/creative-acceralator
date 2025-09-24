from __future__ import annotations

from typing import List

from fastapi import APIRouter, Query

from app.api.state import state
from app.services.aggregation import summarize


router = APIRouter(prefix="/api/summary", tags=["summary"])


@router.get("")
async def get_summary(group_by: str = Query(default="")):
    keys: List[str] = [k for k in group_by.split(",") if k]
    result = summarize(state.evals_for_summary, keys)
    return result
