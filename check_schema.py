"""Checks that the FPL API still has every field this project depends on.

The FPL API is unofficial and undocumented. Its shape has changed before,
most often in July before a new season starts. Run this file whenever
something looks broken, and definitely once every July before the first
deadline:

    python check_schema.py

It prints a plain-English report. A clean run ends with "All checks
passed." Anything else names exactly which insight will be degraded and
why, e.g.:

    MISSING: elements[].expected_goal_involvements
      -> affects: Form vs underlying numbers, Differentials
      -> the FPL API used to call this field 'expected_goal_involvements';
         it may have been renamed or removed. Check the live JSON at
         https://fantasy.premierleague.com/api/bootstrap-static/ and
         update fpl_client.py / insights/ to match.
"""
from __future__ import annotations

import sys

from fpl_client import FPLClient
from settings import TEAM_ID, MINI_LEAGUE_ID

# (path-to-field, list of insights that break if it's missing)
ELEMENT_FIELDS = {
    "id": ["everything -- this is the player identity key"],
    "web_name": ["every table that shows a player name"],
    "team": ["fixture ticker joins, squad review"],
    "element_type": ["position-based tables (Players page, value-by-position)"],
    "now_cost": ["Value, price change watch, transfer legality checks"],
    "total_points": ["Value"],
    "form": ["Captaincy shortlist, form comparisons"],
    "ep_next": ["Captaincy shortlist"],
    "minutes": ["min-minutes filters used across most tables"],
    "selected_by_percent": ["Differentials, mini-league effective ownership"],
    "status": ["Availability risk"],
    "news": ["Availability risk"],
    "chance_of_playing_next_round": ["Availability risk"],
    "transfers_in_event": ["Price change watch"],
    "transfers_out_event": ["Price change watch"],
    "cost_change_event": ["Price change watch"],
    "cost_change_start": ["Price change watch"],
    "expected_goal_involvements": ["Form vs underlying numbers, Differentials"],
    "expected_goals_conceded": ["Form vs underlying numbers (defenders/keepers)"],
    "penalties_order": ["Captaincy shortlist (set-piece duties)"],
    "corners_and_indirect_freekicks_order": ["Captaincy shortlist (set-piece duties)"],
}

TEAM_FIELDS = {
    "id": ["fixture ticker, squad review"],
    "name": ["fixture ticker, squad review"],
    "short_name": ["fixture ticker grid labels"],
}

EVENT_FIELDS = {
    "id": ["gameweek detection"],
    "is_current": ["gameweek detection"],
    "is_next": ["gameweek detection"],
    "finished": ["cache-forever logic, season trend"],
    "deadline_time": ["deadline countdown, reminder email timing"],
}

FIXTURE_FIELDS = {
    "event": ["fixture ticker"],
    "team_h": ["fixture ticker"],
    "team_a": ["fixture ticker"],
    "team_h_difficulty": ["fixture ticker difficulty colouring"],
    "team_a_difficulty": ["fixture ticker difficulty colouring"],
    "kickoff_time": ["fixture ticker, live gameweek detection"],
    "finished": ["double gameweek / blank detection"],
}

ENTRY_FIELDS = {
    "id": ["my squad review"],
    "name": ["site header, email subject"],
    "summary_overall_rank": ["home dashboard"],
    "last_deadline_bank": ["transfer legality (affordability)"],
    "last_deadline_value": ["squad value display"],
}

ENTRY_HISTORY_FIELDS = {
    "current": ["season trend chart"],
    "past": ["season trend chart (prior seasons)"],
    "chips": ["chip context"],
}

PICKS_FIELDS = {
    "picks": ["squad review, captaincy, transfer suggestions"],
    "entry_history": ["bench points wasted, transfer hit cost"],
}

STANDINGS_FIELDS = {
    "standings": ["mini-league table"],
    "league": ["mini-league page header"],
}


def _check(label: str, obj, fields: dict, report: list[str]) -> None:
    if obj is None:
        report.append(f"SKIPPED: {label} -- endpoint returned nothing (see note above)")
        return
    for field, affected in fields.items():
        if field not in obj:
            report.append(
                f"MISSING: {label}.{field}\n"
                f"  -> affects: {', '.join(affected)}"
            )


def main() -> int:
    client = FPLClient()
    report: list[str] = []

    print("Fetching bootstrap-static/ ...")
    bootstrap = client.bootstrap_static()
    elements = bootstrap.get("elements") or []
    teams = bootstrap.get("teams") or []
    events = bootstrap.get("events") or []

    if not elements:
        report.append("MISSING: bootstrap-static -> elements is empty or missing entirely (fatal)")
    else:
        _check("elements[0]", elements[0], ELEMENT_FIELDS, report)

    if not teams:
        report.append("MISSING: bootstrap-static -> teams is empty or missing entirely (fatal)")
    else:
        _check("teams[0]", teams[0], TEAM_FIELDS, report)

    if not events:
        report.append("MISSING: bootstrap-static -> events is empty or missing entirely (fatal)")
    else:
        _check("events[0]", events[0], EVENT_FIELDS, report)

    print("Fetching fixtures/ ...")
    fixtures = client.fixtures()
    if not fixtures:
        report.append("MISSING: fixtures -> empty or missing entirely (fatal)")
    else:
        _check("fixtures[0]", fixtures[0], FIXTURE_FIELDS, report)

    gw_info = client.gameweek_info()
    if gw_info.is_preseason:
        print("Season hasn't started yet (pre-season) -- skipping entry/league checks that "
              "commonly 404 or return empty before GW1.")
    else:
        print(f"Fetching entry/{TEAM_ID}/ ...")
        entry = client.entry(TEAM_ID)
        _check(f"entry/{TEAM_ID}", entry, ENTRY_FIELDS, report)

        print(f"Fetching entry/{TEAM_ID}/history/ ...")
        history = client.entry_history(TEAM_ID)
        _check(f"entry/{TEAM_ID}/history", history, ENTRY_HISTORY_FIELDS, report)

        current_gw = gw_info.current_id or gw_info.next_id
        if current_gw:
            print(f"Fetching entry/{TEAM_ID}/event/{current_gw}/picks/ ...")
            picks = client.entry_picks(TEAM_ID, current_gw, gw_finished=False)
            if picks is None:
                report.append(
                    f"SKIPPED: entry/{TEAM_ID}/event/{current_gw}/picks -- returned nothing. "
                    "Normal if this gameweek's picks aren't locked in yet."
                )
            else:
                _check(f"entry/{TEAM_ID}/event/{current_gw}/picks", picks, PICKS_FIELDS, report)

        print(f"Fetching leagues-classic/{MINI_LEAGUE_ID}/standings/ ...")
        standings = client.league_standings(MINI_LEAGUE_ID)
        _check(f"leagues-classic/{MINI_LEAGUE_ID}/standings", standings, STANDINGS_FIELDS, report)

    print()
    if not report:
        print("All checks passed.")
        return 0

    print(f"{len(report)} issue(s) found:\n")
    for line in report:
        print(line)
        print()
    return 1


if __name__ == "__main__":
    sys.exit(main())
