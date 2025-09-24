from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import List, Optional, Tuple

from app.models.schemas import ImageOut
from app.utils.image_client import GeminiImageClient
from app.utils.storage import to_public_url


@dataclass
class ReferenceImage:
    data: bytes
    mime_type: str


class ImageService:
    def __init__(self) -> None:
        self.cli = GeminiImageClient()

    async def create_images(
        self,
        pairs: List[Tuple[str, str]],
        reference: Optional[ReferenceImage] = None,
    ) -> List[ImageOut]:
        out: List[ImageOut] = []
        for vid, prompt in pairs:
            abs_path = await self.cli.generate_png(prompt, reference)
            url = to_public_url(abs_path)
            out.append(
                ImageOut(
                    id=f"img_{uuid.uuid4().hex[:8]}",
                    variation_id=vid,
                    url=url,
                    provider_meta={
                        "model": getattr(self.cli, "model", ""),
                        "mode": "image-to-image" if reference else "text-to-image",
                    },
                )
            )
        return out
