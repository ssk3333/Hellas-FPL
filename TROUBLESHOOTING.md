# Troubleshooting

Realistic failures this project is likely to hit, what causes them, and what to actually do.
If you're not sure which of these matches what you're seeing, open the failed GitHub Actions run
(Actions tab → click the run → click the red step) and read the last 10-20 lines of its log —
that's usually enough to match it to one of the cases below.

## "503" or "429" errors, especially right around a deadline

**Cause:** The FPL API is unofficial and gets hammered by every FPL tool right before a deadline,
so it throttles or briefly goes down. `fpl_client.py` already retries up to 4 times with backoff
before giving up.

**Fix:** Usually nothing — wait an hour and re-run (or let the next scheduled workflow try again).
If it's still failing hours later and it's nowhere near a deadline, the FPL API itself may just be
down; search "is FPL API down" or check FPL community forums/Reddit, and try again later. This is
not something you can fix by changing this project's code.

## Squad, league, or "my team" pages are empty before the season starts

**Cause:** This is expected, not a bug. Before gameweek 1's deadline, the FPL API's entry/picks/
league endpoints often return nothing (or 404) because your squad isn't "locked in" yet.
`fpl_client.py` detects this (`gw_info.is_preseason`) and every insight function returns an
explicit "not available yet" state instead of crashing.

**Fix:** Nothing to fix. Once gameweek 1's deadline passes, this fills in automatically on the
next site rebuild / email.

## `check_schema.py` reports a MISSING field (usually in July)

**Cause:** The FPL API is undocumented and occasionally renames or removes fields, most often in
the close season before a new year starts. `check_schema.py` checks every field this project
actually uses and tells you in plain English what would break.

**Fix:**
1. Run `.venv/Scripts/python.exe check_schema.py` and read the "affects" line for each missing field.
2. Open `https://fantasy.premierleague.com/api/bootstrap-static/` in a browser and search for a
   similarly-named field — FPL usually renames rather than removes.
3. Update the field name in `insights/common.py` (for player/team fields) or `fpl_client.py`
   (for gameweek/fixture fields), then re-run `check_schema.py` to confirm it's clean, and run
   `pytest` to make sure nothing else broke.
4. If you can't find a replacement field, ask Claude Code to investigate — paste the actual JSON
   from the URL above.

## Resend rejects the email / it never arrives

**Cause:** Without a verified custom domain, Resend's shared sandbox address
(`onboarding@resend.dev`, what this project sends from) can only deliver to the email address
*you* verified when creating your Resend account. If `RECIPIENT_EMAIL` doesn't match that
address, Resend will reject the send.

**Fix:**
1. Check the failed workflow's log for the exact Resend API error message.
2. Log into resend.com and confirm which address is verified on your account.
3. Make sure `RECIPIENT_EMAIL` (in your local `.env` **and** the GitHub Actions secret) matches
   that address exactly.
4. Also check your spam folder — first-time mail from a shared sandbox sender is sometimes
   filtered even when delivery succeeds.

## GitHub Pages isn't showing my latest changes

**Cause:** Either the "Site rebuild" workflow hasn't run since your change, or GitHub's own Pages
deployment (a separate step after your commit lands) hasn't caught up yet — that usually takes
under a minute but can occasionally take a few minutes.

**Fix:**
1. Actions tab → confirm "Site rebuild" has a green check *after* the change you're expecting.
   If not, trigger it manually ("Run workflow") and wait for it to finish.
2. Actions tab → look for a separate "pages build and deployment" run underneath it — that's
   GitHub actually publishing what "Site rebuild" committed. Wait for that to go green too.
3. Hard-refresh the site (Ctrl+Shift+R) — browsers cache pages aggressively.
4. If "Site rebuild" is green but nothing changed, check whether the data itself changed — the
   site only shows what the FPL API currently returns.

## An email or the site fired at a slightly odd time, or seemingly twice

**Cause:** GitHub Actions' cron scheduler is UTC-based and not exact — it can run several minutes
late, and very rarely skips a slot entirely under load. Both email workflows already handle this:
they check local time (`Australia/Hobart`, not raw UTC, so it survives daylight saving) and a
small state file (`data/weekly_state.json` / `data/reminder_state.json`) rather than assuming the
cron fired at exactly the right moment, so a late run still catches the right window and a
double-run can't double-send.

**Fix:** Nothing to fix if only one email actually arrived (check your inbox, not just the
Actions log — a "success" run often means "correctly decided not to send this time," which is
normal). If you genuinely got two emails for the same gameweek, check both
`data/weekly_state.json` and `data/reminder_state.json` in the repo — if either was manually
deleted or edited, the dedup check can't do its job. Don't hand-edit those files.

## Something else entirely

Copy the exact error text (or a screenshot) and describe what you *see*, not what you think is
wrong — "the email arrived but the fixture table was empty" is far more useful than "it's
broken." Claude Code can dig from there.
