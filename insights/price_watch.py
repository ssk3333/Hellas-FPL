"""Insight 5: price change watch.

FPL doesn't publish its real price-change algorithm -- this ranks
players by net transfer momentum (transfers in minus out, this event)
as a rough proxy, alongside the price movement that's already happened
today (cost_change_event) and this season (cost_change_start). Treat
"likely" as a hunch worth a glance the day before a deadline, not a
prediction.
"""
from __future__ import annotations

from insights.common import jsonify, players_df

CAVEAT = (
    "This is an estimate based on net transfer momentum, not FPL's real pricing "
    "formula (which is unpublished and accounts for overall squad ownership, not "
    "just this event's transfers). Use it as a nudge to check closer to the "
    "deadline, not as a guarantee."
)


def price_watch(bootstrap: dict, *, top_n: int = 10) -> dict:
    df = players_df(bootstrap)
    if df.empty:
        return {"likely_to_rise": [], "likely_to_fall": [], "caveat": CAVEAT}

    df = df.copy()
    df["net_momentum"] = df["transfers_in_event"] - df["transfers_out_event"]

    def _record(r):
        return {
            "name": r["web_name"], "team": r["team_short"], "position": r["position"],
            "cost_m": round(r["now_cost_m"], 1),
            "net_transfers_event": int(r["net_momentum"]),
            "already_changed_today_m": round(r["cost_change_event"] / 10, 1),
            "changed_this_season_m": round(r["cost_change_start"] / 10, 1),
        }

    rising = df.sort_values("net_momentum", ascending=False).head(top_n)
    falling = df.sort_values("net_momentum", ascending=True).head(top_n)

    return jsonify({
        "likely_to_rise": [_record(r) for _, r in rising.iterrows()],
        "likely_to_fall": [_record(r) for _, r in falling.iterrows()],
        "caveat": CAVEAT,
    })
