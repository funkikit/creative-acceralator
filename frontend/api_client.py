from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import httpx


class ApiClient:
    """Thin HTTP client for the FastAPI backend.

    This keeps Streamlit UI logic separate from transport and schemas,
    making it easy to swap the UI layer (e.g., Next.js) later.
    """

    def __init__(self, base_url: Optional[str] = None) -> None:
        self.base_url = (base_url or os.getenv("API_BASE_URL") or "http://localhost:8000").rstrip("/")

    def _url(self, path: str) -> str:
        if path.startswith("http://") or path.startswith("https://"):
            return path
        if not path.startswith("/"):
            path = "/" + path
        return f"{self.base_url}{path}"

    def abs_url(self, maybe_relative: str) -> str:
        """Return absolute URL for paths like /static/...."""
        return self._url(maybe_relative)

    def fetch_variation_variables(
        self, goal: str, constraints: List[str], llm: str = "gemini"
    ) -> Dict:
        payload = {"goal": goal, "constraints": constraints, "llm": llm}
        with httpx.Client(timeout=None) as client:
            r = client.post(self._url("/api/variations/variables"), json=payload)
            r.raise_for_status()
            return r.json()

    def create_variations(
        self,
        goal: str,
        dynamic_variables: Dict[str, List[str]],
        constraints: List[str],
        k: int = 8,
        llm: str = "gemini",
        custom_variations: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict:
        payload: Dict[str, Any] = {
            "goal": goal,
            "dynamic_variables": dynamic_variables,
            "constraints": constraints,
            "k": k,
            "llm": llm,
        }
        if custom_variations:
            payload["custom_variations"] = custom_variations
        with httpx.Client(timeout=None) as client:
            r = client.post(self._url("/api/variations"), json=payload)
            r.raise_for_status()
            return r.json()

    def create_images(self, variation_ids: List[str]) -> Dict:
        payload = {"variation_ids": variation_ids}
        with httpx.Client(timeout=None) as client:
            r = client.post(self._url("/api/images"), json=payload)
            r.raise_for_status()
            return r.json()

    def validate(
        self,
        image_ids: List[str],
        n_personas: int = 50,
        llm: str = "openai",
        personas: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict:
        payload = {"image_ids": image_ids, "n_personas": n_personas, "llm": llm}
        if personas:
            payload["personas"] = personas
        with httpx.Client(timeout=None) as client:
            r = client.post(self._url("/api/validate"), json=payload)
            r.raise_for_status()
            return r.json()

    def get_summary(self, group_by: Optional[List[str]] = None) -> Dict:
        keys = ",".join(group_by or [])
        with httpx.Client(timeout=None) as client:
            r = client.get(self._url("/api/summary"), params={"group_by": keys})
            r.raise_for_status()
            return r.json()

    def ping(self) -> Dict:
        with httpx.Client(timeout=5.0) as client:
            r = client.get(self._url("/healthz"))
            r.raise_for_status()
            return r.json()
