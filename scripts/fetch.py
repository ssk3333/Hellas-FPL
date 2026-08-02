"""Quick manual check that the client + config work end to end.

Usage:
    python -m scripts.fetch --show
"""
from __future__ import annotations

import argparse

from fpl_client import FPLClient
from settings import TEAM_ID


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--show", action="store_true",
        help="Print current gameweek, team name, and overall rank.",
    )
    args = parser.parse_args()

    client = FPLClient()
    gw_info = client.gameweek_info()

    if args.show:
        print(f"Current gameweek: {gw_info.current_id}")
        print(f"Next gameweek:    {gw_info.next_id}")
        print(f"Pre-season:       {gw_info.is_preseason}")

        if gw_info.is_preseason:
            print("Team info: season hasn't started yet -- entry endpoints aren't live.")
            return 0

        entry = client.entry(TEAM_ID)
        if entry is None:
            print(f"Team info: no entry found for team ID {TEAM_ID}.")
            return 0

        print(f"Team name:        {entry.get('name', '(unknown)')}")
        print(f"Overall rank:     {entry.get('summary_overall_rank', '(unknown)')}")
        print(f"Overall points:   {entry.get('summary_overall_points', '(unknown)')}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
