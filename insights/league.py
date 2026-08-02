"""Insight 10: mini-league intelligence.

Rank, gap to the leader, and biggest movers come straight from the
standings endpoint. Rival captain/template analysis needs each rival's
`picks` endpoint -- fetching every league member's picks isn't done here
(that's dozens of extra API calls for a mid-sized league), so pass in
whichever `rival_picks_by_entry` you've already fetched for the top
managers you care about; rivals without picks data just won't show a
captain.
"""
from __future__ import annotations

from insights.common import jsonify, players_df

TEMPLATE_OWNERSHIP_THRESHOLD = 30.0


def league_intelligence(
    standings: dict | None, bootstrap: dict, my_team_id: int,
    rival_picks_by_entry: dict[int, dict] | None = None, top_rivals: int = 5,
) -> dict:
    results = ((standings or {}).get("standings") or {}).get("results") or []
    if not results:
        return {"available": False, "reason": "No standings data yet."}

    by_entry = {r.get("entry"): r for r in results}
    me = by_entry.get(my_team_id)
    leader = results[0]

    movers = []
    for r in results:
        last_rank = r.get("last_rank") or r.get("rank")
        movement = (last_rank or 0) - (r.get("rank") or 0)
        movers.append({
            "entry": r.get("entry"), "manager": r.get("player_name"), "team_name": r.get("entry_name"),
            "rank": r.get("rank"), "movement": movement, "total": r.get("total"),
        })
    movers.sort(key=lambda m: m["movement"], reverse=True)

    df = players_df(bootstrap).set_index("id") if bootstrap else None

    # Keys may arrive as strings (e.g. round-tripped through JSON/disk cache)
    # even though `entry` in the standings payload is always an int.
    picks_by_entry = {}
    for k, v in (rival_picks_by_entry or {}).items():
        try:
            picks_by_entry[int(k)] = v
        except (TypeError, ValueError):
            continue

    rivals = []
    for r in results:
        if r.get("entry") == my_team_id:
            continue
        entry_id = r.get("entry")
        rival_info = {
            "entry": entry_id, "manager": r.get("player_name"), "team_name": r.get("entry_name"),
            "rank": r.get("rank"), "total": r.get("total"),
        }
        picks = picks_by_entry.get(entry_id)
        if picks and df is not None:
            captain_pick = next((p for p in picks.get("picks", []) if p.get("is_captain")), None)
            if captain_pick is not None and captain_pick.get("element") in df.index:
                cap_row = df.loc[captain_pick["element"]]
                rival_info["captain"] = cap_row["web_name"]
                rival_info["captain_ownership_pct"] = round(cap_row["selected_by_percent"], 1)
                rival_info["captain_is_template"] = bool(cap_row["selected_by_percent"] >= TEMPLATE_OWNERSHIP_THRESHOLD)
        rivals.append(rival_info)
        if len(rivals) >= top_rivals:
            break

    return jsonify({
        "available": True,
        "my_rank": me.get("rank") if me else None,
        "gap_to_leader": (leader.get("total", 0) - me.get("total", 0)) if me else None,
        "leader": {
            "manager": leader.get("player_name"), "team_name": leader.get("entry_name"), "total": leader.get("total"),
        },
        "biggest_movers_up": [m for m in movers if m["movement"] > 0][:5],
        "biggest_movers_down": [m for m in reversed(movers) if m["movement"] < 0][:5],
        "full_standings": sorted(movers, key=lambda m: m["rank"] or 0),
        "my_team_id": my_team_id,
        "top_rivals": rivals,
        "note": (
            f"\"Template\" here means >={TEMPLATE_OWNERSHIP_THRESHOLD:.0f}% globally owned, not "
            "ownership within your own league specifically -- true in-league effective "
            "ownership needs every manager's picks, which isn't fetched here to keep API "
            "calls reasonable for larger leagues."
        ),
    })
