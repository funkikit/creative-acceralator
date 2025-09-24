from __future__ import annotations

import asyncio
import json
import os
import random
from typing import Literal


class LLMClient:
    def __init__(self, provider: Literal["openai", "gemini"]) -> None:
        self.provider = provider
        self._gemini_model = os.getenv("GEMINI_TEXT_MODEL", "gemini-2.0-flash")
        self._gemini_api_key = os.getenv("GEMINI_API_KEY", "")
        self._openai_model = os.getenv("OPENAI_TEXT_MODEL", "gpt-4o-mini")
        self._openai_api_key = os.getenv("OPENAI_API_KEY", "")

    async def complete(self, system: str, user: str) -> str:
        # Development fallback: enable with LLM_FAKE=1 to avoid external calls.
        if os.getenv("LLM_FAKE", "").lower() in {"1", "true", "yes"}:
            try:
                # If user is JSON, parse it to branch behavior.
                data = json.loads(user)
            except Exception:
                data = None

            # Variation prompt generation path (system passed as a short key in this app)
            if system == "image_prompt" and isinstance(data, dict):
                parts = []
                for k in ("motif", "style", "concept"):
                    v = data.get(k)
                    if v:
                        parts.append(str(v))
                constraints = data.get("constraints") or []
                palette = data.get("palette")
                if palette:
                    parts.append(f"palette:{palette}")
                if constraints:
                    parts.append("; ".join([f"must:{c}" for c in constraints]))
                return "Generate an image of " + ", ".join(parts) if parts else "Simple image prompt"

            # Validator path: build a plausible evaluation JSON
            if isinstance(data, dict) and ("rubric" in data or "persona" in data):
                def rnd() -> float:
                    return round(random.uniform(0.6, 0.95), 3)

                scores = {
                    "Appeal": rnd(),
                    "BrandFit": rnd(),
                    "Originality": rnd(),
                    "Clarity": rnd(),
                    "CulturalSensitivity": rnd(),
                }
                overall = round(sum(scores.values()) / len(scores), 3)
                scores["overall"] = overall
                out = {
                    "scores": scores,
                    "comment": "Looks coherent and on-brief for the target persona.",
                    "flags": [],
                }
                return json.dumps(out, ensure_ascii=False)

            # Variable extraction path: provide deterministic options
            out = {
                "motif": ["sun", "beach", "waves"],
                "style": ["minimal", "flat", "retro"],
                "concept": ["summer", "festival", "music"],
                "constraints": ["A4", "CMYK"],
                "palette": "yellow/blue",
            }
            return json.dumps(out, ensure_ascii=False)

        if self.provider == "gemini":
            return await self._complete_with_gemini(system, user)

        if self.provider == "openai":
            return await self._complete_with_openai(system, user)

        raise NotImplementedError(f"Provider '{self.provider}' is not supported yet.")

    async def _complete_with_gemini(self, system: str, user: str) -> str:
        if not self._gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY is not configured.")

        try:
            import google.generativeai as genai
        except ImportError as exc:  # pragma: no cover - runtime guard only
            raise RuntimeError(
                "google-generativeai is not installed. Run 'uv sync' to install dependencies."
            ) from exc

        def _invoke() -> str:
            genai.configure(api_key=self._gemini_api_key)
            model = genai.GenerativeModel(self._gemini_model)
            prompt = f"{system}\n\n{user}" if system else user
            response = model.generate_content(prompt)
            text = getattr(response, "text", None)
            if not text and getattr(response, "candidates", None):
                parts = response.candidates[0].content.parts
                text = "".join(getattr(part, "text", "") for part in parts)
            if not text:
                raise RuntimeError("Gemini returned an empty response.")
            return text.strip()

        return await asyncio.to_thread(_invoke)

    async def _complete_with_openai(self, system: str, user: str) -> str:
        if not self._openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is not configured.")

        try:
            from openai import AsyncOpenAI
        except ImportError as exc:  # pragma: no cover - runtime guard only
            raise RuntimeError(
                "openai is not installed. Run 'uv sync' to install dependencies."
            ) from exc

        client = AsyncOpenAI(api_key=self._openai_api_key)
        response = await client.chat.completions.create(
            model=self._openai_model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=1.0,
        )

        choice = response.choices[0]
        content = getattr(choice.message, "content", None)
        if isinstance(content, str):
            text = content
        elif isinstance(content, list):  # New responses may be segmented
            parts = []
            for part in content:
                if isinstance(part, dict):
                    part_text = part.get("text")
                    if part_text:
                        parts.append(part_text)
            text = "".join(parts)
        else:
            text = None

        if not text:
            raise RuntimeError("OpenAI returned an empty response.")

        return text.strip()
