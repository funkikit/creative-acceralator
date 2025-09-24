from __future__ import annotations

from typing import Dict, List

import pandas as pd


def summarize(evals: List[Dict], group_keys: List[str]) -> Dict:
    if not evals:
        return {"overall": {"mean_overall": 0.0, "n": 0}, "by_group": [], "ranking": []}

    df = pd.DataFrame(
        [
            {
                "image_id": e["image_id"],
                "persona_id": e["persona_id"],
                "overall": e["scores"]["overall"],
                **e.get("group", {}),
            }
            for e in evals
        ]
    )
    overall = {"mean_overall": float(df["overall"].mean()), "n": int(len(df))}
    by_group: List[Dict] = []
    existing_group_cols = [k for k in group_keys if k in df.columns]
    if existing_group_cols:
        g = df.groupby(existing_group_cols)["overall"].agg(["count", "mean"]).reset_index()
        for _, row in g.iterrows():
            by_group.append(
                {
                    "group": {k: row[k] for k in existing_group_cols},
                    "n": int(row["count"]),
                    "mean_overall": float(row["mean"]),
                }
            )
    ranking_df = (
        df.groupby("image_id")["overall"].mean().sort_values(ascending=False).reset_index()
    )
    ranking = [
        {"image_id": str(r["image_id"]), "overall": float(r["overall"])}
        for _, r in ranking_df.iterrows()
    ]
    return {"overall": overall, "by_group": by_group, "ranking": ranking}
