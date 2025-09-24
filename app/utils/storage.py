from __future__ import annotations

import os
from pathlib import Path


def to_public_url(abs_path: str) -> str:
    static_dir = Path(os.getenv("STATIC_DIR", "tmp")).resolve()
    target = Path(abs_path).resolve()
    try:
        rel = target.relative_to(static_dir)
    except ValueError:
        # fall back to direct name when path is outside static root
        rel = target.name
    return f"/static/{rel.as_posix() if isinstance(rel, Path) else rel}"
