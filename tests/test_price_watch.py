from insights.price_watch import price_watch


def test_rising_and_falling(bootstrap):
    result = price_watch(bootstrap)
    rising_names = [p["name"] for p in result["likely_to_rise"]]
    falling_names = [p["name"] for p in result["likely_to_fall"]]
    assert "Palmer" in rising_names
    assert "De Bruyne" in falling_names
    assert result["caveat"]
