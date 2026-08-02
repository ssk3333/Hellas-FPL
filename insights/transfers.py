"""Insight 9: transfer suggestions.

Every suggestion here is checked against the actual FPL squad rules
before it's shown:

- same position in, same position out (so the 2/5/5/3 squad shape never
  changes -- a like-for-like swap can't break squad validity)
- affordable: incoming player's now_cost <= outgoing player's selling
  price + bank (selling price, not buy price -- FPL's profit rule means
  you don't always get the full purchase price back)
- never more than 3 players from one club after the swap
- a legal starting XI must still exist (checked generically, not assumed)

The expected-points case is our own heuristic (ep_next adjusted by
upcoming fixture difficulty) since the FPL API only gives a single-
gameweek expected-points figure, not a multi-week forecast -- that
uncertainty is stated in the output, not hidden.

Free transfers: the public API doesn't expose how many free transfers
you're currently holding (post-2024 rules let these bank up to 5, and
reconstructing the count needs your full transfer history). Pass
`free_transfers` in if you know it; it defaults to 1, the safe
assumption for "at least one clean transfer available".
"""
from __future__ import annotations

from insights.common import jsonify, players_df
from insights.fixture_ticker import fixture_ticker

MAX_PER_CLUB = 3
HIT_COST = 4
MIN_GAIN_TO_RECOMMEND = 2.0  # per gameweek, before multiplying by the window

METHOD_NOTE = (
    "Expected-points gain is our own estimate: ep_next (FPL's own next-gameweek "
    "projection) adjusted by average fixture difficulty over the window, then "
    "multiplied out. It is not a multi-gameweek FPL forecast -- treat it as a "
    "directional signal, not a precise points total."
)


def _valid_xi_exists(position_counts: dict[str, int]) -> bool:
    """Classic FPL formation rules: exactly 1 GK, 3-5 DEF, 2-5 MID, 1-3 FWD,
    totalling 11. True if the squad's position counts can form one."""
    gkp = position_counts.get("GKP", 0)
    defn = position_counts.get("DEF", 0)
    mid = position_counts.get("MID", 0)
    fwd = position_counts.get("FWD", 0)
    if gkp < 1:
        return False
    for d in range(3, min(defn, 5) + 1):
        for m in range(2, min(mid, 5) + 1):
            f = 11 - 1 - d - m
            if 1 <= f <= min(fwd, 3):
                return True
    return False


def suggest_transfers(
    bootstrap: dict, fixtures: list, picks: dict | None, *, from_gw: int,
    num_gws: int = 4, free_transfers: int = 1, max_suggestions: int = 2,
) -> dict:
    if not picks or not picks.get("picks"):
        return {
            "available": False,
            "reason": "No picks data yet -- season hasn't started, or this gameweek's squad isn't locked in.",
        }

    df = players_df(bootstrap).set_index("id")
    ticker = fixture_ticker(bootstrap, fixtures, from_gw=from_gw, num_gws=num_gws)
    difficulty_by_team = {c["team_id"]: c["mean_difficulty"] for c in ticker["clubs"]}

    squad_picks = {p["element"]: p for p in picks["picks"]}
    squad_ids = set(squad_picks.keys())
    bank_m = (picks.get("entry_history", {}).get("bank", 0) or 0) / 10

    club_counts: dict[int, int] = {}
    position_counts: dict[str, int] = {}
    for pid in squad_ids:
        if pid not in df.index:
            continue
        row = df.loc[pid]
        club_counts[row["team_id"]] = club_counts.get(row["team_id"], 0) + 1
        position_counts[row["position"]] = position_counts.get(row["position"], 0) + 1

    def adjusted_score(row) -> float:
        difficulty = difficulty_by_team.get(row["team_id"])
        adjustment = 0.0 if difficulty is None else -(difficulty - 3) * 0.3
        return (row["ep_next"] + adjustment) * num_gws

    candidates = []
    for out_id in squad_ids:
        if out_id not in df.index:
            continue
        outgoing = df.loc[out_id]
        selling_price_m = (squad_picks[out_id].get("selling_price", outgoing["now_cost_m"] * 10) or 0) / 10
        out_score = adjusted_score(outgoing)

        same_position = df[(df["position"] == outgoing["position"]) & (~df.index.isin(squad_ids))]
        for in_id, incoming in same_position.iterrows():
            budget_m = selling_price_m + bank_m
            if incoming["now_cost_m"] > budget_m + 1e-9:
                continue

            new_club_count = club_counts.get(incoming["team_id"], 0) + (
                0 if incoming["team_id"] == outgoing["team_id"] else 1
            )
            if new_club_count > MAX_PER_CLUB:
                continue

            new_position_counts = dict(position_counts)  # unchanged: like-for-like swap
            if not _valid_xi_exists(new_position_counts):
                continue

            gain = adjusted_score(incoming) - out_score
            candidates.append({
                "out": {"id": int(out_id), "name": outgoing["web_name"], "team": outgoing["team_short"]},
                "in": {"id": int(in_id), "name": incoming["web_name"], "team": incoming["team_short"],
                       "cost_m": round(incoming["now_cost_m"], 1)},
                "position": outgoing["position"],
                "cost_delta_m": round(incoming["now_cost_m"] - selling_price_m, 1),
                "expected_gain": round(gain, 1),
            })

    candidates.sort(key=lambda c: c["expected_gain"], reverse=True)

    suggestions = []
    hits_taken = 0
    for c in candidates:
        if c["expected_gain"] < MIN_GAIN_TO_RECOMMEND * num_gws:
            break
        hit_cost = HIT_COST if len(suggestions) >= free_transfers else 0
        net_gain = c["expected_gain"] - hit_cost
        if hit_cost and net_gain <= 0:
            continue
        c["hit_cost"] = hit_cost
        c["net_expected_gain"] = round(net_gain, 1)
        suggestions.append(c)
        if hit_cost:
            hits_taken += 1
        if len(suggestions) >= max_suggestions:
            break

    if not suggestions:
        return jsonify({
            "available": True,
            "suggestions": [],
            "recommendation": "roll the transfer",
            "reason": (
                "No swap clears the bar of a clear expected-points gain over the next "
                f"{num_gws} gameweeks once fixture difficulty is accounted for. Banking "
                "the free transfer keeps optionality for a bigger move later."
            ),
            "free_transfers_assumed": free_transfers,
            "method_note": METHOD_NOTE,
        })

    return jsonify({
        "available": True,
        "suggestions": suggestions,
        "recommendation": "transfer",
        "free_transfers_assumed": free_transfers,
        "method_note": METHOD_NOTE,
    })
