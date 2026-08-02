"""Insight 2: form vs underlying numbers.

Attackers: actual goals+assists per 90 vs expected_goal_involvements per
90. A big positive gap (delta) means they're scoring more than their
chances deserve -- regression risk. A big negative gap means the chances
are there but the end product isn't -- buy-low candidate, if the chances
keep coming.

Defenders/keepers: ranked by expected_goals_conceded per 90 (lower is
better underlying defence) alongside their actual clean sheet rate, so
you can see whether results match the process.
"""
from __future__ import annotations

import pandas as pd

from insights.common import jsonify, players_df

SMALL_SAMPLE_MINUTES = 450  # ~5 full matches


def _attacker_record(row: pd.Series) -> dict:
    return {
        "name": row["web_name"],
        "team": row["team_short"],
        "position": row["position"],
        "minutes": int(row["minutes"]),
        "ga_per_90": round(row["ga_per_90"], 2) if pd.notna(row["ga_per_90"]) else None,
        "xgi_per_90": round(row["xgi_per_90"], 2) if pd.notna(row["xgi_per_90"]) else None,
        "delta": round(row["delta"], 2) if pd.notna(row["delta"]) else None,
        "small_sample": row["minutes"] < SMALL_SAMPLE_MINUTES,
    }


def form_vs_underlying(bootstrap: dict, *, min_minutes: int = 180, top_n: int = 10) -> dict:
    df = players_df(bootstrap)
    empty = {"overperformers": [], "underperformers": [], "defenders_keepers": [], "note": ""}
    if df.empty:
        return empty

    attackers = df[(df["minutes"] >= min_minutes) & (df["position"].isin(["MID", "FWD"]))].copy()
    if attackers.empty:
        overperformers, underperformers = [], []
    else:
        attackers["delta"] = attackers["ga_per_90"] - attackers["xgi_per_90"]
        attackers = attackers.dropna(subset=["delta"])
        overperformers = [_attacker_record(r) for _, r in attackers.sort_values("delta", ascending=False).head(top_n).iterrows()]
        underperformers = [_attacker_record(r) for _, r in attackers.sort_values("delta", ascending=True).head(top_n).iterrows()]

    dc = df[(df["minutes"] >= min_minutes) & (df["position"].isin(["GKP", "DEF"]))].copy()
    defenders_keepers = []
    if not dc.empty:
        dc["xgc_per_90"] = dc.apply(lambda r: (r["xgc"] / r["nineties"]) if r["nineties"] else None, axis=1)
        dc["clean_sheet_rate"] = dc.apply(lambda r: (r["clean_sheets"] / r["nineties"]) if r["nineties"] else None, axis=1)
        dc = dc.dropna(subset=["xgc_per_90"]).sort_values("xgc_per_90")
        defenders_keepers = [{
            "name": r["web_name"], "team": r["team_short"], "position": r["position"],
            "minutes": int(r["minutes"]),
            "xgc_per_90": round(r["xgc_per_90"], 2),
            "clean_sheet_rate": round(r["clean_sheet_rate"], 2) if pd.notna(r["clean_sheet_rate"]) else None,
            "small_sample": r["minutes"] < SMALL_SAMPLE_MINUTES,
        } for _, r in dc.head(top_n * 2).iterrows()]

    return jsonify({
        "overperformers": overperformers,
        "underperformers": underperformers,
        "defenders_keepers": defenders_keepers,
        "note": (
            "xG-based figures are a proxy, not a guarantee -- a low xGC with a lower-than-expected "
            "clean sheet rate can mean bad luck or a genuinely leaky defence; treat rows marked "
            "small_sample with extra caution."
        ),
    })
