"""The only place in this project that talks to the FPL API.

Every other module should call methods on FPLClient rather than using
`requests` directly, so caching, retries, and defensive parsing stay in
one place. The FPL API (fantasy.premierleague.com/api/) is public,
read-only, and needs no key or login — but it's unofficial, throttles
around deadlines, and occasionally renames fields (see check_schema.py).
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import requests

from settings import CONFIG, ROOT

BASE_URL = "https://fantasy.premierleague.com/api"


class FPLAPIError(RuntimeError):
    """Raised when a request ultimately fails after all retries."""


# ---------------------------------------------------------------------------
# Disk cache
# ---------------------------------------------------------------------------

class DiskCache:
    """A dumb, transparent JSON-file cache keyed by URL + params.

    Each entry is one JSON file: {"fetched_at": <unix ts>, "data": <payload>}.
    A TTL of None means "cache forever" (used for finished-gameweek data,
    which cannot change once the gameweek is over).
    """

    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]
        safe_prefix = "".join(c if c.isalnum() else "_" for c in key)[:40]
        return self.cache_dir / f"{safe_prefix}_{digest}.json"

    def get(self, key: str, ttl_seconds: Optional[float]) -> Optional[Any]:
        path = self._path(key)
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        if ttl_seconds is not None:
            age = time.time() - payload.get("fetched_at", 0)
            if age > ttl_seconds:
                return None
        return payload.get("data")

    def set(self, key: str, data: Any) -> None:
        path = self._path(key)
        payload = {"fetched_at": time.time(), "data": data}
        path.write_text(json.dumps(payload), encoding="utf-8")


# ---------------------------------------------------------------------------
# Gameweek helpers
# ---------------------------------------------------------------------------

@dataclass
class GameweekInfo:
    current_id: Optional[int]
    next_id: Optional[int]
    is_preseason: bool
    is_season_over: bool


def resolve_gameweek(bootstrap: dict) -> GameweekInfo:
    """Works out the current/next gameweek from `events`.

    Primary signal: the `is_current` / `is_next` booleans FPL sets itself.
    Fallback (used if those are ever both missing/false, which happens
    briefly around season rollover): compare each event's `deadline_time`
    against now.
    """
    events = bootstrap.get("events") or []
    current = next((e for e in events if e.get("is_current")), None)
    nxt = next((e for e in events if e.get("is_next")), None)

    if current is None and nxt is None and events:
        now = datetime.now(timezone.utc)
        past_deadlines = []
        future_deadlines = []
        for e in events:
            dt_str = e.get("deadline_time")
            if not dt_str:
                continue
            try:
                dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
            except ValueError:
                continue
            if dt <= now:
                past_deadlines.append((dt, e))
            else:
                future_deadlines.append((dt, e))
        if past_deadlines:
            current = max(past_deadlines, key=lambda pair: pair[0])[1]
        if future_deadlines:
            nxt = min(future_deadlines, key=lambda pair: pair[0])[1]

    is_preseason = current is None and nxt is not None and nxt.get("id") == 1
    is_season_over = current is not None and current.get("id") == len(events) and nxt is None

    return GameweekInfo(
        current_id=current.get("id") if current else None,
        next_id=nxt.get("id") if nxt else None,
        is_preseason=is_preseason,
        is_season_over=is_season_over,
    )


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class FPLClient:
    def __init__(self, config: dict = CONFIG):
        self.config = config
        net = config["network"]
        self.user_agent = net["user_agent"]
        self.max_retries = net["max_retries"]
        self.backoff_base = net["retry_backoff_base_seconds"]
        self.element_summary_delay = net["element_summary_delay_seconds"]

        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self.user_agent})

        cache_cfg = config["cache"]
        self.cache = DiskCache(ROOT / cache_cfg["dir"])
        self.ttl = cache_cfg["ttl_seconds"]

        self._last_element_summary_call = 0.0

    # -- low-level fetch with retry + cache -------------------------------

    def _get(self, path: str, ttl_seconds: Optional[float], *, params: dict | None = None) -> Any:
        cache_key = path if not params else f"{path}?{json.dumps(params, sort_keys=True)}"
        cached = self.cache.get(cache_key, ttl_seconds)
        if cached is not None:
            return cached

        url = f"{BASE_URL}/{path}"
        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                resp = self.session.get(url, params=params, timeout=15)
            except requests.RequestException as exc:
                last_error = exc
            else:
                if resp.status_code == 404:
                    return None
                if resp.status_code in (429, 503):
                    last_error = FPLAPIError(f"{resp.status_code} from {url}")
                elif resp.ok:
                    try:
                        data = resp.json()
                    except ValueError as exc:
                        raise FPLAPIError(f"Non-JSON response from {url}: {exc}") from exc
                    self.cache.set(cache_key, data)
                    return data
                else:
                    resp.raise_for_status()

            if attempt < self.max_retries:
                time.sleep(self.backoff_base ** attempt)

        raise FPLAPIError(
            f"Failed to fetch {url} after {self.max_retries} attempts: {last_error}. "
            "The FPL API is often throttled or briefly down right around deadlines "
            "-- if this is happening then, it usually clears within the hour."
        )

    # -- endpoints ----------------------------------------------------------

    def bootstrap_static(self) -> dict:
        return self._get("bootstrap-static/", self.ttl["bootstrap_static"]) or {}

    def fixtures(self) -> list:
        return self._get("fixtures/", self.ttl["fixtures"]) or []

    def entry(self, team_id: int) -> Optional[dict]:
        """None (not an error) if the team doesn't exist yet, e.g. pre-season."""
        return self._get(f"entry/{team_id}/", self.ttl["bootstrap_static"])

    def entry_history(self, team_id: int) -> Optional[dict]:
        return self._get(f"entry/{team_id}/history/", self.ttl["bootstrap_static"])

    def entry_picks(self, team_id: int, gw: int, *, gw_finished: bool) -> Optional[dict]:
        ttl = None if gw_finished else self.ttl["event_live_active"]
        return self._get(f"entry/{team_id}/event/{gw}/picks/", ttl)

    def entry_transfers(self, team_id: int) -> list:
        return self._get(f"entry/{team_id}/transfers/", self.ttl["event_live_active"]) or []

    def league_standings(self, league_id: int, page: int = 1) -> Optional[dict]:
        return self._get(
            f"leagues-classic/{league_id}/standings/",
            self.ttl["event_live_active"],
            params={"page_standings": page},
        )

    def event_live(self, gw: int, *, gw_finished: bool) -> Optional[dict]:
        ttl = None if gw_finished else self.ttl["event_live_active"]
        return self._get(f"event/{gw}/live/", ttl)

    def element_summary(self, player_id: int) -> Optional[dict]:
        """Per-gameweek history for one player. Only call this for a short-
        list (~60 players max) -- never loop it over the full player list.
        """
        cache_key = f"element-summary/{player_id}/"
        cached = self.cache.get(cache_key, self.ttl["element_summary"])
        if cached is not None:
            return cached

        elapsed = time.time() - self._last_element_summary_call
        if elapsed < self.element_summary_delay:
            time.sleep(self.element_summary_delay - elapsed)

        data = self._get(f"element-summary/{player_id}/", self.ttl["element_summary"])
        self._last_element_summary_call = time.time()
        return data

    # -- convenience ----------------------------------------------------------

    def gameweek_info(self) -> GameweekInfo:
        return resolve_gameweek(self.bootstrap_static())
