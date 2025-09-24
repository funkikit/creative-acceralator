from __future__ import annotations

import base64
import os
import pathlib
import uuid

import asyncio


class GeminiImageClient:
    def __init__(self) -> None:
        self.api_key = os.environ.get("GEMINI_API_KEY", "")
        self.model = os.getenv("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image-preview")
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
            try:
                response = client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                )
            except genai.errors.ClientError as exc:
                status = getattr(exc, "status_code", None)
                if status == 404:
                    raise RuntimeError(
                        "指定されたGeminiモデルが見つかりませんでした。APIキーの権限とモデル名(GEMINI_IMAGE_MODEL)を確認してください。"
                    ) from exc
                raise RuntimeError(f"Gemini API呼び出しに失敗しました: {exc}") from exc

            images: list[bytes] = []
            rai_reasons: list[str] = []
            safety_flags: list[str] = []

            for candidate in response.candidates or []:
                for rating in getattr(candidate, "safety_ratings", []) or []:
                    probability = getattr(rating, "probability", None)
                    category = getattr(rating, "category", None)
                    prob_label = getattr(probability, "name", None) or str(probability)
                    if prob_label.upper() in {"MEDIUM", "HIGH", "VERY_HIGH"}:
                        safety_flags.append(f"{category}: {prob_label}")

                content = getattr(candidate, "content", None)
                if not content:
                    continue

                for part in getattr(content, "parts", []) or []:
                    inline = getattr(part, "inline_data", None)
                    if inline and getattr(inline, "data", None):
                        data = inline.data
                        if isinstance(data, bytes):
                            images.append(data)
                        else:
                            images.append(base64.b64decode(data))
                    text = getattr(part, "text", None)
                    if text:
                        rai_reasons.append(text)

            if images:
                return images[0]

            feedback = getattr(response, "prompt_feedback", None)
            if feedback:
                block_reason = getattr(feedback, "block_reason", None)
                if block_reason:
                    raise RuntimeError(
                        "Geminiの安全フィードバックにより画像生成がブロックされました: "
                        f"{block_reason}"
                    )

            if safety_flags:
                raise RuntimeError(
                    "Geminiの安全フィルタにより画像が拒否されました: " + ", ".join(safety_flags)
                )

            if rai_reasons:
                raise RuntimeError(
                    "Geminiから画像が返されず、テキスト応答が返却されました: "
                    + " | ".join(rai_reasons)
                )

            raise RuntimeError("Geminiから画像データが取得できませんでした。")

        raw = await asyncio.to_thread(_invoke)
        img_id = f"img_{uuid.uuid4().hex[:8]}"
        out = self.static_dir / f"{img_id}.png"
        out.write_bytes(raw)
        return str(out.resolve())
