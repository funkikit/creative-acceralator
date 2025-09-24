from __future__ import annotations

import csv
import random
import uuid
from typing import Dict, List


def _normalize_gender(value: str) -> str:
    mapping = {"F": "Female", "M": "Male"}
    return mapping.get(value, value.title())


def _normalize_familiarity(value: str) -> str:
    mapping = {"high": "high", "medium": "medium", "low": "low"}
    return mapping.get(value.lower(), value)


def build_persona_summary(row: Dict[str, str]) -> str:
    gender = _normalize_gender(row.get("gender", ""))
    familiarity = _normalize_familiarity(row.get("familiarity", ""))
    region = row.get("region", "").upper()
    background = row.get("background", "")
    age_band = row.get("age_band", "")
    bits = [part for part in [age_band, gender, background] if part]
    headline = " ".join(bits)
    tail = f"based in {region} with {familiarity} familiarity".strip()
    return f"{headline} {tail}".strip()


def sample_personas(n: int, seed_csv: str) -> List[Dict]:
    """seed_csv の分布に基づき n 件のペルソナ属性を合成"""
    rows: List[Dict] = []
    with open(seed_csv, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows.append(r)
    out: List[Dict] = []
    for _ in range(n):
        r = random.choice(rows)
        out.append(
            {
                "id": f"p_{uuid.uuid4().hex[:6]}",
                "gender": r["gender"],
                "age_band": r["age_band"],
                "region": r["region"],
                "background": r["background"],
                "familiarity": r["familiarity"],
                "summary": build_persona_summary(r),
                "extras": {},
            }
        )
    return out
