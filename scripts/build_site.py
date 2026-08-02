"""Builds the static site into docs/, published by GitHub Pages.

Usage:
    python -m scripts.build_site

Every insight function already degrades gracefully when data isn't
available yet (pre-season, gameweek not locked in, etc.) -- this script's
job is just to fetch, call each insight once, and hand the results to
Jinja2. Templates check `.available` flags and render an explanatory
empty state rather than assuming the happy path.
"""
from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from jinja2 import Environment, FileSystemLoader, select_autoescape

from fpl_client import FPLClient
from insights.availability import availability_risk
from insights.captaincy import captaincy_shortlist
from insights.chips import chip_context
from insights.common import is_flagged, jsonify, players_df
from insights.differentials import differentials
from insights.fixture_ticker import fixture_ticker
from insights.league import league_intelligence
from insights.price_watch import price_watch
from insights.squad import squad_review
from insights.transfers import suggest_transfers
from insights.trend import season_trend
from insights.underlying import form_vs_underlying
from insights.value import value_tables
from settings import CONFIG, MINI_LEAGUE_ID, ROOT, SITE_NAME, SITE_TIMEZONE, TEAM_ID

DOCS_DIR = ROOT / "docs"
TEMPLATES_DIR = ROOT / "templates"
STATIC_DIR = ROOT / "static"
TOP_RIVALS = 5


def _tz() -> ZoneInfo:
    return ZoneInfo(SITE_TIMEZONE)


def _format_local(dt_utc: datetime) -> str:
    return dt_utc.astimezone(_tz()).strftime("%a %d %b, %H:%M")


def _parse_iso(value: str | None):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Tiny dependency-free SVG line chart for the season trend panel
# ---------------------------------------------------------------------------

def render_trend_svg(values: list[float], labels: list[str], *, width=560, height=160,
                      invert_y=False, pad=28) -> str:
    if not values or all(v is None for v in values):
        return ""
    clean = [v for v in values if v is not None]
    lo, hi = min(clean), max(clean)
    if lo == hi:
        lo -= 1
        hi += 1
    if invert_y:
        lo, hi = hi, lo  # lower rank number plots higher on the chart

    n = len(values)
    x_step = (width - 2 * pad) / max(n - 1, 1)

    def y_of(v: float) -> float:
        return pad + (hi - v) / (hi - lo) * (height - 2 * pad) if invert_y else \
            pad + (1 - (v - lo) / (hi - lo)) * (height - 2 * pad)

    points = []
    for i, v in enumerate(values):
        if v is None:
            continue
        x = pad + i * x_step
        y = y_of(v)
        points.append((x, y))

    path = " ".join(f"{'M' if i == 0 else 'L'}{x:.1f},{y:.1f}" for i, (x, y) in enumerate(points))
    circles = "".join(f'<circle class="point" cx="{x:.1f}" cy="{y:.1f}" r="3"></circle>' for x, y in points)
    label_els = "".join(
        f'<text x="{pad + i * x_step:.1f}" y="{height - 6}" text-anchor="middle">{labels[i]}</text>'
        for i in range(n)
    )

    return (
        f'<svg class="trend-chart" viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="Trend chart across {n} gameweeks">'
        f'<line class="axis" x1="{pad}" y1="{height - pad}" x2="{width - pad}" y2="{height - pad}"></line>'
        f'<path class="line" d="{path}"></path>{circles}{label_els}</svg>'
    )


# ---------------------------------------------------------------------------
# Players table JSON blob (for players.js)
# ---------------------------------------------------------------------------

def players_table_rows(bootstrap: dict) -> list[dict]:
    df = players_df(bootstrap)
    if df.empty:
        return []
    df = df[df["now_cost_m"] > 0].copy()
    df["points_per_million"] = df["total_points"] / df["now_cost_m"]
    rows = [{
        "name": r["web_name"], "team": r["team_short"], "position": r["position"],
        "cost_m": round(r["now_cost_m"], 1), "total_points": int(r["total_points"]),
        "form": round(r["form"], 1), "ownership_pct": round(r["selected_by_percent"], 1),
        "points_per_million": round(r["points_per_million"], 2),
        "flagged": is_flagged(r["status"], r["chance_of_playing_next_round"]),
    } for _, r in df.iterrows()]
    return jsonify(rows)


# ---------------------------------------------------------------------------
# Data gathering
# ---------------------------------------------------------------------------

def gather_data(client: FPLClient) -> dict:
    bootstrap = client.bootstrap_static()
    fixtures = client.fixtures()
    gw_info = client.gameweek_info()
    from_gw = gw_info.next_id or gw_info.current_id

    events = {e.get("id"): e for e in (bootstrap.get("events") or [])}
    deadline_dt = _parse_iso((events.get(from_gw) or {}).get("deadline_time")) if from_gw else None

    min_minutes = CONFIG["insights"]["min_minutes_for_form"]
    ownership_max = CONFIG["insights"]["differential_ownership_pct_max"]

    ticker = (
        fixture_ticker(bootstrap, fixtures, from_gw=from_gw, num_gws=6)
        if from_gw else {"clubs": [], "from_gw": None, "num_gws": 6}
    )
    underlying = form_vs_underlying(bootstrap, min_minutes=min_minutes)
    value = value_tables(bootstrap, min_minutes=min_minutes)
    diffs = (
        differentials(bootstrap, fixtures, from_gw=from_gw, ownership_max=ownership_max, min_minutes=min_minutes)
        if from_gw else []
    )
    prices = price_watch(bootstrap)
    captaincy = (
        captaincy_shortlist(bootstrap, fixtures, from_gw=from_gw, differential_ownership_max=ownership_max)
        if from_gw else {"shortlist": [], "safe_pick": None, "differential_pick": None, "note": ""}
    )

    # Entry-dependent data: fpl_client already returns None on 404, which is
    # exactly what happens for all of these before the season starts.
    entry = client.entry(TEAM_ID)
    history = client.entry_history(TEAM_ID)
    current_gw = gw_info.current_id
    gw_finished = bool((events.get(current_gw) or {}).get("finished")) if current_gw else False
    picks = client.entry_picks(TEAM_ID, current_gw, gw_finished=gw_finished) if current_gw else None
    raw_transfers = client.entry_transfers(TEAM_ID)
    standings = client.league_standings(MINI_LEAGUE_ID)

    trend = season_trend(history)
    chips = chip_context(history, ticker)

    squad = (
        squad_review(bootstrap, fixtures, picks, from_gw=from_gw, num_gws=3)
        if from_gw else {"available": False, "reason": "No gameweek data yet."}
    )

    my_availability = []
    if picks and picks.get("picks"):
        squad_ids = [p.get("element") for p in picks["picks"]]
        my_availability = availability_risk(bootstrap, player_ids=squad_ids)

    transfers = (
        suggest_transfers(bootstrap, fixtures, picks, from_gw=from_gw, free_transfers=1)
        if from_gw else {"available": False, "reason": "No gameweek data yet."}
    )

    league = {"available": False, "reason": "No standings data yet."}
    if standings and (standings.get("standings") or {}).get("results"):
        rival_entries = [
            r["entry"] for r in standings["standings"]["results"] if r.get("entry") != TEAM_ID
        ][:TOP_RIVALS]
        rival_picks = {}
        if current_gw:
            for rid in rival_entries:
                rp = client.entry_picks(rid, current_gw, gw_finished=gw_finished)
                if rp:
                    rival_picks[rid] = rp
        league = league_intelligence(
            standings, bootstrap, my_team_id=TEAM_ID, rival_picks_by_entry=rival_picks, top_rivals=TOP_RIVALS,
        )

    all_players_df = players_df(bootstrap)
    df_players = all_players_df.set_index("id") if not all_players_df.empty else None
    transfer_history = []
    for t in (raw_transfers or [])[-15:][::-1]:
        in_id, out_id = t.get("element_in"), t.get("element_out")
        in_name = df_players.loc[in_id]["web_name"] if df_players is not None and in_id in df_players.index else f"#{in_id}"
        out_name = df_players.loc[out_id]["web_name"] if df_players is not None and out_id in df_players.index else f"#{out_id}"
        transfer_history.append({
            "gw": t.get("event"), "in": in_name, "out": out_name,
            "in_cost_m": (t.get("element_in_cost") or 0) / 10,
            "out_cost_m": (t.get("element_out_cost") or 0) / 10,
            "time": t.get("time"),
        })

    points_svg = render_trend_svg(
        [g["points"] for g in trend.get("gameweeks", [])],
        [f"GW{g['gw']}" for g in trend.get("gameweeks", [])],
    ) if trend.get("available") else ""
    rank_svg = render_trend_svg(
        [g["overall_rank"] for g in trend.get("gameweeks", [])],
        [f"GW{g['gw']}" for g in trend.get("gameweeks", [])],
        invert_y=True,
    ) if trend.get("available") else ""

    generated_at_utc = datetime.now(timezone.utc)

    return {
        "site_name": SITE_NAME,
        "timezone_label": SITE_TIMEZONE,
        "generated_at": _format_local(generated_at_utc),
        "gw_display": from_gw or "--",
        "deadline_iso": deadline_dt.isoformat() if deadline_dt else None,
        "deadline_local": _format_local(deadline_dt) if deadline_dt else None,
        "preseason": gw_info.is_preseason,
        "entry_name": (entry or {}).get("name"),
        "ticker": ticker,
        "underlying": underlying,
        "value": value,
        "differentials": diffs[:12],
        "prices": prices,
        "captaincy": captaincy,
        "squad": squad,
        "my_availability": my_availability,
        "transfers": transfers,
        "league": league,
        "trend": trend,
        "chips": chips,
        "transfer_history": transfer_history,
        "points_svg": points_svg,
        "rank_svg": rank_svg,
        # escape "</" so a player/club name can never prematurely close the
        # surrounding <script> tag it's embedded in
        "players_json": json.dumps(players_table_rows(bootstrap)).replace("</", "<\\/"),
        "players_count": len(all_players_df),
    }


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

PAGES = [
    ("index.html", "index.html", "home"),
    ("players.html", "players.html", "players"),
    ("fixtures.html", "fixtures.html", "fixtures"),
    ("my-team.html", "my_team.html", "my_team"),
    ("league.html", "league.html", "league"),
]


def build(client: FPLClient | None = None) -> None:
    client = client or FPLClient()
    data = gather_data(client)

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html"]),
    )

    if DOCS_DIR.exists():
        shutil.rmtree(DOCS_DIR)
    DOCS_DIR.mkdir(parents=True)

    for out_name, template_name, page_key in PAGES:
        template = env.get_template(template_name)
        html = template.render(page=page_key, **data)
        (DOCS_DIR / out_name).write_text(html, encoding="utf-8")

    assets_dir = DOCS_DIR / "assets"
    assets_dir.mkdir(parents=True)
    shutil.copy(STATIC_DIR / "css" / "style.css", assets_dir / "style.css")
    shutil.copy(STATIC_DIR / "js" / "site.js", assets_dir / "site.js")
    shutil.copy(STATIC_DIR / "js" / "players.js", assets_dir / "players.js")

    (DOCS_DIR / ".nojekyll").write_text("", encoding="utf-8")

    print(f"Built {len(PAGES)} pages into {DOCS_DIR}")


if __name__ == "__main__":
    build()
