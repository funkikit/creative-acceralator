from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Any


@dataclass
class AppState:
    variations: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    images: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    evaluations: List[Dict[str, Any]] = field(default_factory=list)
    evals_for_summary: List[Dict[str, Any]] = field(default_factory=list)


state = AppState()

