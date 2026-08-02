"""Insight 1: fixture ticker.

Next N gameweeks per club, home/away marked, ranked by mean difficulty.
Double gameweeks (2+ fixtures in one event) and blanks (0 fixtures) are
called out explicitly since they matter more than any single rating.
"""
from __future__ import annotations

from insights.common import fixtures_df, jsonify, teams_df


def fixture_ticker(bootstrap: dict, fixtures: list, *, from_gw: int, num_gws: int = 6) -> dict:
    teams = teams_df(bootstrap)
    fx = fixtures_df(fixtures)
    target_gws = list(range(from_gw, from_gw + num_gws))

    if teams.empty:
        return {"from_gw": from_gw, "num_gws": num_gws, "clubs": []}

    fx = fx[fx["event"].isin(target_gws)] if not fx.empty else fx
    team_lookup = teams.set_index("id").to_dict("index")

    clubs = []
    for tid, info in team_lookup.items():
        gameweeks = []
        for gw in target_gws:
            matches = []
            if not fx.empty:
                gw_fx = fx[fx["event"] == gw]
                for _, r in gw_fx[gw_fx["team_h"] == tid].iterrows():
                    matches.append({"opponent_id": r["team_a"], "home": True, "difficulty": r["team_h_difficulty"]})
                for _, r in gw_fx[gw_fx["team_a"] == tid].iterrows():
                    matches.append({"opponent_id": r["team_h"], "home": False, "difficulty": r["team_a_difficulty"]})
            for m in matches:
                opp = team_lookup.get(m["opponent_id"], {})
                m["opponent_short"] = opp.get("short_name", "UNK")
            gameweeks.append({"gw": gw, "matches": matches})

        all_difficulties = [m["difficulty"] for gwk in gameweeks for m in gwk["matches"] if m["difficulty"] is not None]
        mean_difficulty = round(sum(all_difficulties) / len(all_difficulties), 2) if all_difficulties else None

        clubs.append({
            "team_id": tid,
            "team_name": info.get("name", "Unknown"),
            "team_short": info.get("short_name", "UNK"),
            "gameweeks": gameweeks,
            "mean_difficulty": mean_difficulty,
            "double_gws": [gwk["gw"] for gwk in gameweeks if len(gwk["matches"]) >= 2],
            "blank_gws": [gwk["gw"] for gwk in gameweeks if len(gwk["matches"]) == 0],
        })

    clubs.sort(key=lambda c: (c["mean_difficulty"] is None, c["mean_difficulty"]))
    for rank, club in enumerate(clubs, start=1):
        club["rank"] = rank

    return jsonify({"from_gw": from_gw, "num_gws": num_gws, "clubs": clubs})
