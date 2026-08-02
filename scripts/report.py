"""Prints the captain shortlist and fixture ticker to the terminal.

Usage:
    python -m scripts.report
"""
from __future__ import annotations

from fpl_client import FPLClient
from insights.captaincy import captaincy_shortlist
from insights.fixture_ticker import fixture_ticker
from settings import CONFIG


def main() -> int:
    client = FPLClient()
    gw_info = client.gameweek_info()
    from_gw = gw_info.next_id or gw_info.current_id

    if from_gw is None:
        print("No upcoming or current gameweek found -- season may be over, or bootstrap-static is empty.")
        return 0

    if gw_info.is_preseason:
        print(f"Pre-season: showing gameweek {from_gw} (the season opener) as the reference point.\n")

    bootstrap = client.bootstrap_static()
    fixtures = client.fixtures()

    print(f"=== Fixture ticker (from GW{from_gw}, next 6 gameweeks) ===\n")
    ticker = fixture_ticker(bootstrap, fixtures, from_gw=from_gw, num_gws=6)
    for club in ticker["clubs"]:
        diff = f"{club['mean_difficulty']:.2f}" if club["mean_difficulty"] is not None else "n/a"
        flags = []
        if club["double_gws"]:
            flags.append(f"DOUBLE gw{club['double_gws']}")
        if club["blank_gws"]:
            flags.append(f"BLANK gw{club['blank_gws']}")
        flag_str = f"  [{', '.join(flags)}]" if flags else ""
        print(f"{club['rank']:>2}. {club['team_short']:<4} mean FDR {diff}{flag_str}")

    print(f"\n=== Captaincy shortlist (GW{from_gw}) ===\n")
    captaincy = captaincy_shortlist(
        bootstrap, fixtures, from_gw=from_gw,
        differential_ownership_max=CONFIG["insights"]["differential_ownership_pct_max"],
    )
    if not captaincy["shortlist"]:
        print("No eligible candidates -- likely no fixture data for this gameweek yet.")
    else:
        for i, c in enumerate(captaincy["shortlist"], start=1):
            print(f"{i}. {c['name']} ({c['team']}) -- {c['rationale']} -- score {c['score']}")
        print(f"\nSafe pick: {captaincy['safe_pick']['name']} ({captaincy['safe_pick']['ownership_pct']}% owned)")
        if captaincy["differential_pick"]:
            print(
                f"Differential pick: {captaincy['differential_pick']['name']} "
                f"({captaincy['differential_pick']['ownership_pct']}% owned)"
            )
        print(f"\nNote: {captaincy['note']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
