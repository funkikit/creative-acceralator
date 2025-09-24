from __future__ import annotations

from typing import List, Tuple

from fastapi import APIRouter

from app.api.state import state
from app.models.schemas import ImagesRequest, ImagesResponse
from app.services.image_gen import ImageService


router = APIRouter(prefix="/api/images", tags=["images"])


@router.post("", response_model=ImagesResponse)
async def create_images(req: ImagesRequest):
    pairs: List[Tuple[str, str]] = []
    for vid in req.variation_ids:
        meta = state.variations.get(vid)
        if not meta:
            continue
        pairs.append((vid, meta["prompt"]))
    images = await ImageService().create_images(pairs)
    for img in images:
        state.images[img.id] = img.model_dump()
    return ImagesResponse(images=images)
