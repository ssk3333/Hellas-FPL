"""Loads config.yaml and .env once, for every other module to import.

Kept deliberately tiny: no dependency on python-dotenv, just a minimal
KEY=VALUE parser, since the brief asks before adding new dependencies.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv(ROOT / ".env")


def load_config(path: Path | None = None) -> dict[str, Any]:
    path = path or ROOT / "config.yaml"
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


CONFIG: dict[str, Any] = load_config()

TEAM_ID: int = CONFIG["fpl"]["team_id"]
MINI_LEAGUE_ID: int = CONFIG["fpl"]["mini_league_id"]
SITE_TIMEZONE: str = CONFIG["site"]["timezone"]
SITE_NAME: str = CONFIG["site"]["name"]

RECIPIENT_EMAIL: str | None = os.environ.get("RECIPIENT_EMAIL")
RESEND_API_KEY: str | None = os.environ.get("RESEND_API_KEY")
