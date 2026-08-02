"""Shared DataFrame builders used by every insight module.

Centralising this here means the "don't index a dict directly" rule only
has to be followed in one place: every field pulled off the raw FPL JSON
goes through `.get()` with a sensible default before it becomes a
DataFrame column.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

POSITION_NAMES = {1: "GKP", 2: "DEF", 3: "MID", 4: "FWD"}


def jsonify(obj):
    """Recursively converts numpy/pandas scalar types (np.True_, np.float64,
    np.int64 -- what you get back from iterating DataFrame rows) into plain
    Python types. Every insight function's return value should pass through
    this once, at the end, so callers (site JSON blobs, email templates,
    tests) never have to think about it again."""
    if isinstance(obj, dict):
        return {k: jsonify(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [jsonify(v) for v in obj]
    if isinstance(obj, np.generic):
        return obj.item()
    return obj


def to_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def to_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def format_money(millions: float) -> str:
    return f"£{millions:.1f}m"


def players_df(bootstrap: dict) -> pd.DataFrame:
    """One row per player. now_cost is FPL's tenths-of-a-million integer;
    exposed here as `now_cost_m` in real millions."""
    elements = bootstrap.get("elements") or []
    teams = {t.get("id"): t for t in (bootstrap.get("teams") or [])}

    rows = []
    for el in elements:
        team = teams.get(el.get("team"), {})
        minutes = to_int(el.get("minutes"))
        nineties = minutes / 90 if minutes else None
        goals = to_int(el.get("goals_scored"))
        assists = to_int(el.get("assists"))
        xgi = to_float(el.get("expected_goal_involvements"))
        rows.append({
            "id": el.get("id"),
            "web_name": el.get("web_name") or "Unknown",
            "team_id": el.get("team"),
            "team_name": team.get("name") or "Unknown",
            "team_short": team.get("short_name") or "UNK",
            "position": POSITION_NAMES.get(el.get("element_type"), "UNK"),
            "now_cost_m": to_float(el.get("now_cost")) / 10,
            "total_points": to_int(el.get("total_points")),
            "form": to_float(el.get("form")),
            "ep_next": to_float(el.get("ep_next")),
            "minutes": minutes,
            "nineties": nineties,
            "selected_by_percent": to_float(el.get("selected_by_percent")),
            "status": el.get("status") or "a",
            "news": el.get("news") or "",
            "news_added": el.get("news_added"),
            "chance_of_playing_next_round": el.get("chance_of_playing_next_round"),
            "transfers_in_event": to_int(el.get("transfers_in_event")),
            "transfers_out_event": to_int(el.get("transfers_out_event")),
            "cost_change_event": to_int(el.get("cost_change_event")),
            "cost_change_start": to_int(el.get("cost_change_start")),
            "xgi": xgi,
            "xgc": to_float(el.get("expected_goals_conceded")),
            "goals_scored": goals,
            "assists": assists,
            "clean_sheets": to_int(el.get("clean_sheets")),
            "penalties_order": el.get("penalties_order"),
            "set_piece_order": el.get("corners_and_indirect_freekicks_order"),
            "ga_per_90": ((goals + assists) / nineties) if nineties else None,
            "xgi_per_90": (xgi / nineties) if nineties else None,
        })

    df = pd.DataFrame(rows)
    if not df.empty:
        df["points_per_90"] = df.apply(
            lambda r: (r["total_points"] / r["nineties"]) if r["nineties"] else None, axis=1
        )
    return df


def teams_df(bootstrap: dict) -> pd.DataFrame:
    teams = bootstrap.get("teams") or []
    return pd.DataFrame([
        {"id": t.get("id"), "name": t.get("name") or "Unknown", "short_name": t.get("short_name") or "UNK"}
        for t in teams
    ])


def fixtures_df(fixtures: list) -> pd.DataFrame:
    rows = [{
        "event": f.get("event"),
        "team_h": f.get("team_h"),
        "team_a": f.get("team_a"),
        "team_h_difficulty": f.get("team_h_difficulty"),
        "team_a_difficulty": f.get("team_a_difficulty"),
        "kickoff_time": f.get("kickoff_time"),
        "finished": bool(f.get("finished", False)),
    } for f in (fixtures or [])]
    return pd.DataFrame(rows)


def is_flagged(status: str, chance_of_playing) -> bool:
    """True if a player has any availability doubt.

    `chance_of_playing_next_round` is None when FPL has no fitness
    concern logged -- that means fully available, not "unknown risk".
    """
    if status and status != "a":
        return True
    if chance_of_playing is not None and chance_of_playing < 100:
        return True
    return False
