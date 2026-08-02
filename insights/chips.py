"""Insight 12: chip context.

Which chips you still have available, from your history's `chips` list,
plus a plain-English note on whether the fixture ticker's doubles/blanks
suggest a chip would be worth playing soon. This does NOT know FPL's
exact wildcard reset date for the second half of the season -- that
detail changes and isn't in the public API, so it's flagged rather than
guessed.
"""
from __future__ import annotations

STANDARD_CHIP_COUNTS = {"wildcard": 2, "freehit": 1, "bboost": 1, "3xc": 1}
CHIP_LABELS = {"wildcard": "Wildcard", "freehit": "Free Hit", "bboost": "Bench Boost", "3xc": "Triple Captain"}


def chip_context(history: dict | None, ticker: dict) -> dict:
    used_events = (history or {}).get("chips") or []
    used_counts: dict[str, int] = {}
    for c in used_events:
        name = c.get("name")
        if name:
            used_counts[name] = used_counts.get(name, 0) + 1

    available = {
        name: max(0, STANDARD_CHIP_COUNTS[name] - used_counts.get(name, 0))
        for name in STANDARD_CHIP_COUNTS
    }

    clubs = ticker.get("clubs", []) if ticker else []
    doubles = sorted({gw for c in clubs for gw in c.get("double_gws", [])})
    blanks = sorted({gw for c in clubs for gw in c.get("blank_gws", [])})

    notes = []
    if available.get("bboost") and doubles:
        notes.append(
            f"Bench Boost: gameweek {doubles[0]} has at least one club with a double fixture -- "
            "worth checking whether your bench players are involved before you decide."
        )
    if available.get("3xc") and doubles:
        notes.append(
            f"Triple Captain: gameweek {doubles[0]} is worth a look if your best captain option "
            "has a double that week."
        )
    if available.get("freehit") and blanks:
        notes.append(
            f"Free Hit: gameweek {blanks[0]} has at least one club blanking -- worth checking "
            "whether that hits several of your squad at once."
        )
    if available.get("wildcard"):
        notes.append(
            "Wildcard: FPL resets to a fresh wildcard partway through the season and it doesn't "
            "carry over -- the exact reset date isn't in the public API, so check the official "
            "FPL site if timing matters to your plan."
        )
    if not notes:
        notes.append("No chip currently looks obviously worth playing from the fixture data alone.")

    return {
        "available_chips": {CHIP_LABELS[k]: v for k, v in available.items()},
        "used_chips": [{"chip": CHIP_LABELS.get(c.get("name"), c.get("name")), "gw": c.get("event")} for c in used_events],
        "notes": notes,
    }
