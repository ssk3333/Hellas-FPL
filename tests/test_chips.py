from insights.chips import chip_context
from insights.fixture_ticker import fixture_ticker


def test_chip_availability_and_notes(bootstrap, fixtures, history):
    ticker = fixture_ticker(bootstrap, fixtures, from_gw=4, num_gws=3)  # covers the gw5 double + blank
    result = chip_context(history, ticker)
    assert result["available_chips"]["Wildcard"] == 1  # one of two used
    assert result["available_chips"]["Bench Boost"] == 1
    assert any("Bench Boost" in n for n in result["notes"])


def test_no_history_still_returns_standard_counts():
    ticker = {"clubs": []}
    result = chip_context(None, ticker)
    assert result["available_chips"]["Wildcard"] == 2
