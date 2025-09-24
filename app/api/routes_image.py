from __future__ import annotations

import base64
import binascii
from typing import List, Tuple, Optional

from fastapi import APIRouter, HTTPException

from app.api.state import state
from app.models.schemas import ImagesRequest, ImagesResponse
from app.services.image_gen import ImageService, ReferenceImage


router = APIRouter(prefix="/api/images", tags=["images"])


@router.post("", response_model=ImagesResponse)
async def create_images(req: ImagesRequest):
    pairs: List[Tuple[str, str]] = []
    for vid in req.variation_ids:
        meta = state.variations.get(vid)
        if not meta:
            continue
        pairs.append((vid, meta["prompt"]))
    reference: Optional[ReferenceImage] = None
    if req.reference_image:
        try:
            raw = base64.b64decode(req.reference_image.data, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise HTTPException(status_code=400, detail="参照画像の形式が不正です") from exc
        mime_type = req.reference_image.mime_type or ""
        if not mime_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="参照画像のMIMEタイプが不正です")
        reference = ReferenceImage(data=raw, mime_type=mime_type)
    images = await ImageService().create_images(pairs, reference)
    for img in images:
        state.images[img.id] = img.model_dump()
    return ImagesResponse(images=images)
