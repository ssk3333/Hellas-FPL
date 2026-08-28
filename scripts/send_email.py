"""Sends the weekly digest email or the pre-deadline reminder via Resend.

Usage:
    python -m scripts.send_email                       # weekly digest -- sends once, any
                                                           # time from Thursday's scheduled
                                                           # hour through the deadline
    python -m scripts.send_email --dry-run              # writes email_preview.html, no send
    python -m scripts.send_email --force                 # weekly digest, ignore the
                                                           # day/hour/dedup gate
    python -m scripts.send_email --mode reminder         # reminder, only sends if the
                                                           # next deadline is actually close
    python -m scripts.send_email --mode reminder --force # bypass the timing/dedup gate

Both modes are safe to run on a frequent cron (e.g. hourly): each one
decides for itself whether it's actually the right moment to send, using
local time (not UTC, so it survives daylight saving) plus a state file so
a delayed or re-triggered run can never double-send. --force skips that
gate for manual testing, regardless of --dry-run.

Reuses scripts.build_site.gather_data() so the email shows exactly the
same insight data as the site, computed the same way.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from jinja2 import Environment, FileSystemLoader, select_autoescape

from fpl_client import FPLClient
from scripts.build_site import gather_data
from settings import CONFIG, RECIPIENT_EMAIL, RESEND_API_KEY, ROOT, SITE_NAME, SITE_TIMEZONE

TEMPLATES_DIR = ROOT / "templates" / "email"
WEEKLY_STATE_FILE = ROOT / "data" / "weekly_state.json"
REMINDER_STATE_FILE = ROOT / "data" / "reminder_state.json"
RESEND_URL = "https://api.resend.com/emails"
DEFAULT_FROM = f"{SITE_NAME} <onboarding@resend.dev>"
THURSDAY = 3  # datetime.weekday(): Monday=0


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html"]),
    )


def _headline(data: dict) -> str:
    transfers = data["transfers"]
    if transfers.get("available") and transfers.get("suggestions"):
        top = transfers["suggestions"][0]
        return f"{top['out']['name']} -> {top['in']['name']}"
    if transfers.get("available"):
        return transfers.get("recommendation", "see this week's report").capitalize()
    return "this week's report"


def _site_url(data: dict) -> str | None:
    base_url = (CONFIG.get("site") or {}).get("base_url")
    return base_url or None


def render_weekly(data: dict) -> tuple[str, str, str]:
    env = _env()
    context = {**data, "site_url": _site_url(data)}
    context["preheader"] = (
        f"GW{data['gw_display']} deadline {data['deadline_local']} -- {_headline(data)}"
    )
    subject = f"GW{data['gw_display']} deadline {data['deadline_local']} -- {_headline(data)}"
    html = env.get_template("weekly.html").render(**context)
    text = env.get_template("weekly.txt").render(**context)
    return subject, html, text


def render_reminder(data: dict, hours_until: float) -> tuple[str, str, str]:
    env = _env()
    context = {**data, "site_url": _site_url(data), "hours_until": round(hours_until, 1)}
    subject = f"Deadline in {round(hours_until, 1)}h -- GW{data['gw_display']} -- {_headline(data)}"
    html = env.get_template("reminder.html").render(**context)
    text = env.get_template("reminder.txt").render(**context)
    return subject, html, text


def _load_state(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def _save_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state), encoding="utf-8")


def send_via_resend(subject: str, html: str, text: str, to_address: str) -> None:
    if not RESEND_API_KEY:
        raise RuntimeError(
            "RESEND_API_KEY isn't set. Add it to .env locally, or as a GitHub Actions "
            "secret when running in CI. See README.md for how to get one from resend.com."
        )
    resp = requests.post(
        RESEND_URL,
        headers={"Authorization": f"Bearer {RESEND_API_KEY}", "Content-Type": "application/json"},
        json={"from": DEFAULT_FROM, "to": [to_address], "subject": subject, "html": html, "text": text},
        timeout=15,
    )
    if not resp.ok:
        raise RuntimeError(f"Resend API error {resp.status_code}: {resp.text}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["weekly", "reminder"], default="weekly")
    parser.add_argument("--dry-run", action="store_true", help="Write a preview file instead of sending.")
    parser.add_argument("--force", action="store_true", help="Ignore the timing/dedup gate for this mode.")
    parser.add_argument("--to", default=RECIPIENT_EMAIL, help="Override the recipient address.")
    args = parser.parse_args()

    if not args.to and not args.dry_run:
        print("No recipient set. Add RECIPIENT_EMAIL to .env or pass --to.")
        return 1

    client = FPLClient()
    data = gather_data(client)

    if args.mode == "weekly":
        now_local = datetime.now(ZoneInfo(SITE_TIMEZONE))
        send_hour = CONFIG["email"]["send_hour_local"]

        if not args.force:
            # GitHub's `schedule` trigger is documented as best-effort: under load it can be
            # delayed by hours or dropped for an entire run, with no guarantee (confirmed
            # in practice -- a ~33h gap in this repo's own run history swallowed the exact
            # hour this used to require). So instead of requiring exactly Thursday at
            # send_hour, this is a catch-up window: any time from Thursday send_hour through
            # the upcoming deadline, still gated to once per week by the state file below.
            on_or_after_thursday = now_local.weekday() > THURSDAY
            is_thursday_at_or_after_send_hour = (
                now_local.weekday() == THURSDAY and now_local.hour >= send_hour
            )
            time_ok = on_or_after_thursday or is_thursday_at_or_after_send_hour

            deadline_passed = False
            if data.get("deadline_iso"):
                deadline_dt = datetime.fromisoformat(data["deadline_iso"])
                deadline_passed = datetime.now(timezone.utc) >= deadline_dt

            if not time_ok or deadline_passed:
                print(
                    f"It's {now_local.strftime('%A %H:%M')} in {SITE_TIMEZONE} -- scheduled "
                    f"send window is Thursday {send_hour:02d}:00 through the deadline. Nothing sent."
                )
                return 0
            iso_year, iso_week, _ = now_local.isocalendar()
            week_key = f"{iso_year}-W{iso_week:02d}"
            state = _load_state(WEEKLY_STATE_FILE)
            if state.get("last_weekly_sent") == week_key:
                print(f"Weekly email already sent for {week_key}. Nothing sent.")
                return 0

        subject, html, text = render_weekly(data)
    else:
        if not data.get("deadline_iso"):
            print("No upcoming deadline found -- nothing to remind about.")
            return 0
        deadline_dt = datetime.fromisoformat(data["deadline_iso"])
        hours_until = (deadline_dt - datetime.now(timezone.utc)).total_seconds() / 3600
        threshold = CONFIG["email"]["reminder_hours_before_deadline"]

        if not args.force:
            if hours_until <= 0 or hours_until > threshold:
                print(f"Deadline is {hours_until:.1f}h away -- outside the {threshold}h reminder window. Nothing sent.")
                return 0
            state = _load_state(REMINDER_STATE_FILE)
            if state.get("last_reminder_sent_gw") == data["gw_display"]:
                print(f"Reminder already sent for GW{data['gw_display']}. Nothing sent.")
                return 0

        subject, html, text = render_reminder(data, hours_until)

    if args.dry_run:
        preview_path = ROOT / "email_preview.html"
        preview_path.write_text(html, encoding="utf-8")
        print(f"Subject: {subject}")
        print(f"Wrote preview to {preview_path}")
        return 0

    send_via_resend(subject, html, text, args.to)
    print(f"Sent to {args.to}: {subject}")

    if args.mode == "reminder":
        _save_state(REMINDER_STATE_FILE, {"last_reminder_sent_gw": data["gw_display"]})
    else:
        now_local = datetime.now(ZoneInfo(SITE_TIMEZONE))
        iso_year, iso_week, _ = now_local.isocalendar()
        _save_state(WEEKLY_STATE_FILE, {"last_weekly_sent": f"{iso_year}-W{iso_week:02d}"})

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
