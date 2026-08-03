# Hellas FPL

A personal Fantasy Premier League insights system: a website ([live here](https://ssk3333.github.io/Hellas-FPL/))
and a weekly email, both built from the free public FPL API. It runs on its own, in the cloud,
on a schedule — you don't need to keep your computer on or run anything yourself day to day.

This README is written assuming no coding background. If a term isn't explained the first
time it's used, ask whoever is helping you (or search it) rather than guessing.

## What's actually running, and when

| Workflow | Schedule | What it does |
|---|---|---|
| **Site rebuild** | Every 6 hours | Re-fetches data from the FPL API and republishes the site |
| **Weekly email** | Checked hourly, only sends Thursday 08:00 `Australia/Hobart` | Sends the full digest email |
| **Deadline reminder** | Checked hourly, only sends when the next deadline is within 9 hours | Sends a short reminder email |

All three live under the **Actions** tab of the GitHub repo. A green check mark means it ran
fine (even if it decided not to send anything that hour — that's normal and expected most of the
time). A red X means something broke — see [TROUBLESHOOTING.md](TROUBLESHOOTING.md).

## Changing your team, league, or site name

Open [config.yaml](config.yaml) and edit these values, then either wait for the next scheduled
site rebuild or trigger it by hand (Actions → "Site rebuild" → "Run workflow"):

- `fpl.team_id` — your FPL team ID
- `fpl.mini_league_id` — your mini-league ID
- `site.name` — the name shown on the site and in emails

Do **not** put your email address in this file — it's committed to git and this repo is public.
Your recipient email and Resend API key live in `.env` locally and as GitHub Actions secrets
(Settings → Secrets and variables → Actions) — update both places if either ever changes.

## What each file does

**Root**
- `config.yaml` — your team/league IDs, site name, timezone, and tunable thresholds. Safe to edit; contains no secrets.
- `settings.py` — loads `config.yaml` and `.env` once, for every other file to import.
- `fpl_client.py` — the only file that talks to the FPL API. Handles caching, retries, and gracefully returning "no data" instead of crashing when an endpoint is empty (e.g. pre-season).
- `check_schema.py` — run this every July. Checks that the FPL API still has every field this project depends on, in plain English.
- `requirements.txt` — the Python packages this project needs.
- `.env.example` — copy this to `.env` and fill in your own values; `.env` is never committed.
- `.gitignore` — tells git which files to never commit (your `.env`, the `cache/` folder, etc.).

**`insights/`** — one file per insight from the brief (fixture ticker, form vs underlying
numbers, value, differentials, price watch, availability risk, captaincy shortlist, squad
review, transfer suggestions, mini-league intelligence, season trend, chip context).
`common.py` holds shared helpers used by all of them.

**`scripts/`** — the things you or a workflow actually run:
- `fetch.py` — quick manual check that the API connection works (`--show` prints current gameweek/team/rank)
- `report.py` — prints the fixture ticker and captaincy shortlist to your terminal
- `build_site.py` — rebuilds the whole website into `docs/`
- `send_email.py` — sends the weekly digest or the deadline reminder (see below for flags)

**`templates/`** — the Jinja2 (HTML-with-placeholders) files `build_site.py` and `send_email.py`
fill in with real data. `templates/email/` holds the email versions specifically.

**`static/`** — the site's CSS and JavaScript, copied into `docs/assets/` on every build.

**`docs/`** — the actual built website. GitHub Pages serves this folder directly. Don't hand-edit
files in here — they get overwritten on the next rebuild.

**`tests/`** — automated tests for the `insights/` package, run against a fake sample API
response in `tests/fixtures/` so they never touch the real internet.

**`cache/`** — downloaded API responses, kept locally so repeated runs don't hammer the FPL API. Safe to delete; it'll just refill itself.

**`data/weekly_state.json`, `data/reminder_state.json`** — small tracking files so the automated
emails can't accidentally send twice. Don't edit these by hand.

**`.github/workflows/`** — the three schedules described above.

## Re-running things by hand

All commands below assume you're inside the `fpl_insights` folder, using the project's own
Python (not your system Python) — that's what `.venv/Scripts/python.exe` means below.

```bash
# Check the API connection and see your current gameweek/team/rank
.venv/Scripts/python.exe -m scripts.fetch --show

# Print the fixture ticker and captaincy shortlist to your terminal
.venv/Scripts/python.exe -m scripts.report

# Rebuild the website into docs/ (open docs/index.html afterward to check it)
.venv/Scripts/python.exe -m scripts.build_site

# Preview the weekly email without sending it (writes email_preview.html)
.venv/Scripts/python.exe -m scripts.send_email --dry-run

# Actually send the weekly email right now, bypassing the "is it Thursday 8am" check
.venv/Scripts/python.exe -m scripts.send_email --force

# Preview or force-send the deadline reminder the same way
.venv/Scripts/python.exe -m scripts.send_email --mode reminder --dry-run
.venv/Scripts/python.exe -m scripts.send_email --mode reminder --force

# Run the automated tests
.venv/Scripts/python.exe -m pytest -q
```

You can also trigger any of the three scheduled workflows manually from GitHub: go to the
**Actions** tab, click the workflow name on the left, then "Run workflow".

## When a workflow shows a red X

Click the failed run to read its log — the last few lines usually say plainly what went wrong.
The most common causes, and what to do about each, are in [TROUBLESHOOTING.md](TROUBLESHOOTING.md).
If it's genuinely unclear, copy the last 10–20 lines of the log and ask whoever set this up for you
(or Claude Code) to explain it.

## Every July, before the new season

FPL's API occasionally changes field names, almost always in the run-up to a new season. Run:

```bash
.venv/Scripts/python.exe check_schema.py
```

It ends with "All checks passed" if nothing's changed, or a plain-English list of exactly what
broke and which part of the site/email it affects.

## Honest limits

This system has no access to bookmaker odds, lineup news, or minutes projections — the three
things that most affect real FPL decisions. It's good at surfacing structure (fixtures, value,
underlying numbers, your own blind spots), not at predicting who starts on Saturday. Several
figures (the captaincy score, the transfer expected-gain, the price-change watch) are our own
estimates built on top of what the FPL API actually gives us, not official FPL numbers — each is
labelled as such in the site and email where it appears.
