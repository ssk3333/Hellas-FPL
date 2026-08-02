from insights.transfers import _valid_xi_exists, suggest_transfers


def test_valid_xi_exists_standard_squad():
    assert _valid_xi_exists({"GKP": 2, "DEF": 5, "MID": 5, "FWD": 3}) is True


def test_valid_xi_exists_impossible_squad():
    assert _valid_xi_exists({"GKP": 0, "DEF": 5, "MID": 5, "FWD": 3}) is False


def test_no_data_without_picks(bootstrap, fixtures):
    result = suggest_transfers(bootstrap, fixtures, None, from_gw=3)
    assert result["available"] is False


def test_suggestions_never_break_club_limit(bootstrap, fixtures, picks):
    result = suggest_transfers(bootstrap, fixtures, picks, from_gw=3, num_gws=4, free_transfers=1)
    assert result["available"] is True
    starting_counts = {"ARS": 3, "MCI": 3, "LIV": 3, "CHE": 3, "TOT": 3}
    for s in result.get("suggestions", []):
        projected = dict(starting_counts)
        projected[s["out"]["team"]] -= 1
        projected[s["in"]["team"]] = projected.get(s["in"]["team"], 0) + 1
        assert all(count <= 3 for count in projected.values()), s


def test_suggestions_are_affordable(bootstrap, fixtures, picks):
    result = suggest_transfers(bootstrap, fixtures, picks, from_gw=3, num_gws=4, free_transfers=1)
    for s in result.get("suggestions", []):
        assert s["cost_delta_m"] <= 5.0 + 1e-9  # bank (0.5m) + max plausible selling price headroom in this fixture
