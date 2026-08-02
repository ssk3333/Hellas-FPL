"""Insight 4: differentials -- strong underlying numbers, good upcoming
fixtures, and low ownership. Ownership is always shown next to the name
so you can judge the risk yourself rather than trusting a single score.
"""
from __future__ import annotations

from insights.common import jsonify, players_df
from insights.fixture_ticker import fixture_ticker


def differentials(
    bootstrap: dict, fixtures: list, *, from_gw: int, num_gws: int = 6,
    ownership_max: float = 10.0, min_minutes: int = 180, top_n: int = 15,
) -> list[dict]:
    df = players_df(bootstrap)
    if df.empty:
        return []

    ticker = fixture_ticker(bootstrap, fixtures, from_gw=from_gw, num_gws=num_gws)
    difficulty_by_team = {c["team_id"]: c["mean_difficulty"] for c in ticker["clubs"]}

    pool = df[(df["minutes"] >= min_minutes) & (df["selected_by_percent"] < ownership_max)].copy()
    if pool.empty:
        return []

    def underlying_score(row) -> float | None:
        if row["position"] in ("MID", "FWD"):
            return row["xgi_per_90"]
        if row["nineties"]:
            return -(row["xgc"] / row["nineties"])
        return None

    pool["underlying_score"] = pool.apply(underlying_score, axis=1)
    pool["fixture_difficulty"] = pool["team_id"].map(difficulty_by_team)
    pool = pool.dropna(subset=["underlying_score"])

    pool = pool.sort_values(
        by=["fixture_difficulty", "underlying_score"],
        ascending=[True, False],
        na_position="last",
    )

    return jsonify([{
        "name": r["web_name"], "team": r["team_short"], "position": r["position"],
        "ownership_pct": round(r["selected_by_percent"], 1),
        "cost_m": round(r["now_cost_m"], 1),
        "underlying_score": round(r["underlying_score"], 2),
        "fixture_difficulty": r["fixture_difficulty"],
        "minutes": int(r["minutes"]),
        "small_sample": r["minutes"] < 450,
    } for _, r in pool.head(top_n).iterrows()])
