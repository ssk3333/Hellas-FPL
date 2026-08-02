import json
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load(name: str):
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


@pytest.fixture
def bootstrap():
    return _load("sample_bootstrap.json")


@pytest.fixture
def fixtures():
    return _load("sample_fixtures.json")


@pytest.fixture
def entry():
    return _load("sample_entry.json")


@pytest.fixture
def history():
    return _load("sample_history.json")


@pytest.fixture
def picks():
    return _load("sample_picks.json")


@pytest.fixture
def standings():
    return _load("sample_standings.json")


@pytest.fixture
def rival_picks():
    return _load("sample_rival_picks.json")
