"""Insight 7: captaincy shortlist.

Ranks the top candidates for next gameweek using `ep_next` (FPL's own
expected-points-next-gameweek estimate) adjusted by fixture difficulty
and home advantage, with a small bonus for set-piece/penalty duties.
Players with no fixture next gameweek (a blank) or an availability flag
are excluded outright. The composite score is our own heuristic, not an
FPL number -- said explicitly in the output.

Every entry gets a one-line rationale. The top-ownership candidate among
the shortlist is marked as the "safe" pick; the lowest-ownership
candidate that still clears a reasonable score is the "differential" pick.
"""
from __future__ import annotations

from insights.common import is_flagged, jsonify, players_df
from insights.fixture_ticker import fixture_ticker

SCORE_NOTE = (
    "Score = ep_next adjusted for fixture difficulty, home advantage, and set-piece "
    "duties -- our own composite heuristic, not an official FPL figure. Minutes shown "
    "are season-to-date totals, not a rolling recent-form window (the FPL API doesn't "
    "expose per-match minutes in bootstrap-static)."
)


def _rationale(row: dict) -> str:
    parts = [f"vs {row['opponent']} ({'H' if row['home'] else 'A'})", f"FDR {row['difficulty']}"]
    parts.append(f"ep_next {row['ep_next']:.1f}")
    if row["penalties_order"] == 1:
        parts.append("takes penalties")
    if row["set_piece_order"] == 1:
        parts.append("first on corners/free-kicks")
    return ", ".join(parts)


def captaincy_shortlist(
    bootstrap: dict, fixtures: list, *, from_gw: int,
    top_n: int = 8, differential_ownership_max: float = 10.0,
) -> dict:
    df = players_df(bootstrap)
    if df.empty:
        return {"shortlist": [], "safe_pick": None, "differential_pick": None, "note": SCORE_NOTE}

    ticker = fixture_ticker(bootstrap, fixtures, from_gw=from_gw, num_gws=1)
    next_fixture_by_team: dict[int, dict] = {}
    for club in ticker["clubs"]:
        matches = club["gameweeks"][0]["matches"] if club["gameweeks"] else []
        if matches:
            next_fixture_by_team[club["team_id"]] = matches[0]

    candidates = []
    for _, r in df.iterrows():
        if is_flagged(r["status"], r["chance_of_playing_next_round"]):
            continue
        fixture = next_fixture_by_team.get(r["team_id"])
        if fixture is None:
            continue  # blank gameweek for this club
        difficulty = fixture.get("difficulty") or 3
        home = bool(fixture.get("home"))

        score = r["ep_next"]
        score -= (difficulty - 3) * 0.5
        score += 0.3 if home else 0.0
        if r["penalties_order"] == 1:
            score += 0.5
        elif r["set_piece_order"] == 1:
            score += 0.3

        candidates.append({
            "id": int(r["id"]), "name": r["web_name"], "team": r["team_short"], "position": r["position"],
            "opponent": fixture.get("opponent_short", "UNK"), "home": home, "difficulty": difficulty,
            "ep_next": r["ep_next"], "form": r["form"], "minutes": int(r["minutes"]),
            "ownership_pct": round(r["selected_by_percent"], 1),
            "penalties_order": r["penalties_order"], "set_piece_order": r["set_piece_order"],
            "score": round(score, 2),
        })

    candidates.sort(key=lambda c: c["score"], reverse=True)
    shortlist = candidates[:top_n]
    for c in shortlist:
        c["rationale"] = _rationale(c)

    safe_pick = max(shortlist, key=lambda c: c["ownership_pct"], default=None)
    differential_candidates = [c for c in shortlist if c["ownership_pct"] < differential_ownership_max]
    differential_pick = differential_candidates[0] if differential_candidates else None

    return jsonify({
        "shortlist": shortlist,
        "safe_pick": safe_pick,
        "differential_pick": differential_pick,
        "note": SCORE_NOTE,
    })
