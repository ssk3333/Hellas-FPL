"""Insight 6: availability risk.

Flags anyone whose `status` isn't 'a' (available) or whose
`chance_of_playing_next_round` is below 100, with FPL's own `news` text
and the date it was added. Pass `player_ids` to restrict to your squad
or a shortlist; omit it to scan the whole player pool (used for the
site's full risk table).
"""
from __future__ import annotations

from insights.common import is_flagged, jsonify, players_df

STATUS_LABELS = {
    "a": "Available", "d": "Doubtful", "i": "Injured",
    "s": "Suspended", "u": "Unavailable", "n": "Not available",
}


def availability_risk(bootstrap: dict, player_ids: list[int] | None = None) -> list[dict]:
    df = players_df(bootstrap)
    if df.empty:
        return []

    if player_ids is not None:
        df = df[df["id"].isin(player_ids)]

    df = df[df.apply(lambda r: is_flagged(r["status"], r["chance_of_playing_next_round"]), axis=1)]

    return jsonify([{
        "id": int(r["id"]), "name": r["web_name"], "team": r["team_short"], "position": r["position"],
        "status": r["status"],
        "status_label": STATUS_LABELS.get(r["status"], r["status"]),
        "chance_of_playing_next_round": r["chance_of_playing_next_round"],
        "news": r["news"] or "No further detail given.",
        "news_added": r["news_added"],
    } for _, r in df.sort_values("web_name").iterrows()])
