"""Insight 3: value -- points per £m and form per £m, split by position,
with a minimum-minutes threshold so unplayed bench fodder can't top the
table just because it's cheap and has zero points diluting nothing."""
from __future__ import annotations

import pandas as pd

from insights.common import jsonify, players_df


def value_tables(bootstrap: dict, *, min_minutes: int = 180, top_n: int = 15) -> dict:
    df = players_df(bootstrap)
    if df.empty:
        return {}

    eligible = df[df["minutes"] >= min_minutes].copy()
    eligible = eligible[eligible["now_cost_m"] > 0]
    eligible["points_per_million"] = eligible["total_points"] / eligible["now_cost_m"]
    eligible["form_per_million"] = eligible["form"] / eligible["now_cost_m"]

    out: dict[str, list] = {}
    for position in ["GKP", "DEF", "MID", "FWD"]:
        pos_df = eligible[eligible["position"] == position].sort_values("points_per_million", ascending=False)
        out[position] = [{
            "name": r["web_name"], "team": r["team_short"],
            "cost_m": round(r["now_cost_m"], 1),
            "total_points": int(r["total_points"]),
            "points_per_million": round(r["points_per_million"], 2),
            "form_per_million": round(r["form_per_million"], 2) if pd.notna(r["form_per_million"]) else None,
        } for _, r in pos_df.head(top_n).iterrows()]

    return jsonify(out)
