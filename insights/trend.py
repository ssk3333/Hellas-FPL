"""Insight 11: my season trend.

Points and overall rank per gameweek, straight from the `history`
endpoint's `current` list, plus season totals for bench points wasted
and hit costs paid.
"""
from __future__ import annotations


def season_trend(history: dict | None) -> dict:
    current = (history or {}).get("current") or []
    if not current:
        return {"available": False, "reason": "No history yet -- season hasn't started, or no gameweeks played."}

    gameweeks = [{
        "gw": g.get("event"),
        "points": g.get("points"),
        "total_points": g.get("total_points"),
        "overall_rank": g.get("overall_rank"),
        "bench_points": g.get("points_on_bench") or 0,
        "hit_cost": g.get("event_transfers_cost") or 0,
        "value_m": (g.get("value") or 0) / 10,
        "bank_m": (g.get("bank") or 0) / 10,
    } for g in current]

    return {
        "available": True,
        "gameweeks": gameweeks,
        "total_bench_points_wasted": sum(g["bench_points"] for g in gameweeks),
        "total_hits_cost": sum(g["hit_cost"] for g in gameweeks),
        "past_seasons": (history or {}).get("past") or [],
    }
