from __future__ import annotations

import base64
import os
import pathlib
import uuid

import asyncio


class GeminiImageClient:
    def __init__(self) -> None:
        self.api_key = os.environ.get("GEMINI_API_KEY", "")
        self.model = os.getenv("GEMINI_IMAGE_MODEL", "gemini-nanobanana")
        self.static_dir = pathlib.Path(os.getenv("STATIC_DIR", "tmp"))
        self.static_dir.mkdir(parents=True, exist_ok=True)

    async def generate_png(self, prompt: str) -> str:
        # Development fallback: if IMAGE_FAKE=1, create a placeholder PNG locally.
        if os.getenv("IMAGE_FAKE", "").lower() in {"1", "true", "yes"}:
            # 1x1 transparent PNG
            tiny_png_b64 = (
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGMAAQAABQAB"
                "J2kq0QAAAABJRU5ErkJggg=="
            )
            img_id = f"img_{uuid.uuid4().hex[:8]}"
            out = self.static_dir / f"{img_id}.png"
            out.write_bytes(base64.b64decode(tiny_png_b64))
            return str(out.resolve())

        if not self.api_key:
            # Fallback to placeholder if key is missing (dev-friendly default)
            img_id = f"img_{uuid.uuid4().hex[:8]}"
            out = self.static_dir / f"{img_id}.png"
            # 1x1 transparent PNG
            out.write_bytes(base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGMAAQAABQABJ2kq0QAAAABJRU5ErkJggg=="
            ))
            return str(out.resolve())

        return await self._generate_via_gemini(prompt)

    async def _generate_via_gemini(self, prompt: str) -> str:
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY is not configured.")

        def _invoke() -> bytes:
            try:
                from google import genai
            except ImportError as exc:  # pragma: no cover - optional dependency
                raise RuntimeError(
                    "google-genai is not installed. Run 'uv sync' to install dependencies."
                ) from exc

            client = genai.Client(api_key=self.api_key)
            response = client.models.generate_content(
                model=self.model,
                contents=[prompt],
            )

            for candidate in response.candidates or []:
                parts = getattr(candidate.content, "parts", [])
                for part in parts:
                    inline = getattr(part, "inline_data", None)
                    if inline and getattr(inline, "data", None):
                        data = inline.data
                        if isinstance(data, bytes):
                            return data
                        return base64.b64decode(data)
            raise RuntimeError("Geminiから画像データが取得できませんでした。")

        raw = await asyncio.to_thread(_invoke)
        img_id = f"img_{uuid.uuid4().hex[:8]}"
        out = self.static_dir / f"{img_id}.png"
        out.write_bytes(raw)
        return str(out.resolve())
