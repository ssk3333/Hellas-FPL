"""Insight 8: my squad review.

Pulls your current 15 from the `picks` endpoint, shows each player's next
N fixtures and form, flags anyone the availability-risk insight would
flag, and identifies your three weakest holdings plus any bench-order
issue (a flagged/injured player sitting above a fit one, which wastes
autosub priority if both end up unable to play).
"""
from __future__ import annotations

from insights.availability import STATUS_LABELS
from insights.common import is_flagged, jsonify, players_df
from insights.fixture_ticker import fixture_ticker


def squad_review(bootstrap: dict, fixtures: list, picks: dict | None, *, from_gw: int, num_gws: int = 3) -> dict:
    if not picks or not picks.get("picks"):
        return {
            "available": False,
            "reason": "No picks data yet -- season hasn't started, or this gameweek's squad isn't locked in.",
        }

    df = players_df(bootstrap).set_index("id")
    ticker = fixture_ticker(bootstrap, fixtures, from_gw=from_gw, num_gws=num_gws)
    fixtures_by_team = {c["team_id"]: c["gameweeks"] for c in ticker["clubs"]}

    squad = []
    for p in picks["picks"]:
        pid = p.get("element")
        if pid not in df.index:
            continue
        row = df.loc[pid]
        next_fx = fixtures_by_team.get(row["team_id"], [])
        next_summaries = []
        for gwk in next_fx:
            if not gwk["matches"]:
                next_summaries.append("BLANK")
            else:
                next_summaries.append("/".join(
                    f"{m['opponent_short']}({'H' if m['home'] else 'A'})" for m in gwk["matches"]
                ))
        squad.append({
            "id": int(pid), "name": row["web_name"], "team": row["team_short"], "position": row["position"],
            "slot": p.get("position"),
            "is_starting": (p.get("position") or 99) <= 11,
            "is_captain": bool(p.get("is_captain")),
            "is_vice_captain": bool(p.get("is_vice_captain")),
            "multiplier": p.get("multiplier", 1),
            "form": row["form"], "total_points": int(row["total_points"]),
            "next_fixtures": next_summaries,
            "flagged": is_flagged(row["status"], row["chance_of_playing_next_round"]),
            "status_label": STATUS_LABELS.get(row["status"], row["status"]),
        })

    squad.sort(key=lambda s: s["slot"] or 99)

    starters = [s for s in squad if s["is_starting"]]
    ranked_worst_first = sorted(starters, key=lambda s: (not s["flagged"], s["form"]))
    weakest_3 = []
    for s in ranked_worst_first:
        reasons = []
        if s["flagged"]:
            reasons.append(f"availability flag ({s['status_label']})")
        if s["form"] < 2:
            reasons.append(f"low form ({s['form']})")
        if "BLANK" in s["next_fixtures"]:
            reasons.append("blank gameweek coming up")
        if reasons:
            weakest_3.append({**s, "reasons": reasons})
        if len(weakest_3) == 3:
            break

    bench = [s for s in squad if not s["is_starting"]]
    bench_order_issue = None
    for i in range(len(bench) - 1):
        if bench[i]["flagged"] and not bench[i + 1]["flagged"]:
            bench_order_issue = (
                f"{bench[i]['name']} (flagged: {bench[i]['status_label']}) is above "
                f"{bench[i + 1]['name']} (fit) in your bench order -- if both end up "
                f"unavailable, the fit player should be autosubbed in first."
            )
            break

    entry_history = picks.get("entry_history") or {}
    return jsonify({
        "available": True,
        "squad": squad,
        "weakest_3": weakest_3,
        "bench_order_issue": bench_order_issue,
        "bank_m": (entry_history.get("bank", 0) or 0) / 10,
        "value_m": (entry_history.get("value", 0) or 0) / 10,
        "event_transfers": entry_history.get("event_transfers", 0),
        "points_on_bench": entry_history.get("points_on_bench", 0),
    })
