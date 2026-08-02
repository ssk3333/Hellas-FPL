from insights.fixture_ticker import fixture_ticker


def test_detects_double_and_blank(bootstrap, fixtures):
    result = fixture_ticker(bootstrap, fixtures, from_gw=4, num_gws=3)  # gw4, 5, 6
    by_short = {c["team_short"]: c for c in result["clubs"]}
    assert 5 in by_short["MCI"]["double_gws"]
    assert 5 in by_short["LIV"]["blank_gws"]


def test_ranks_by_mean_difficulty(bootstrap, fixtures):
    result = fixture_ticker(bootstrap, fixtures, from_gw=1, num_gws=6)
    ranks = [c["rank"] for c in result["clubs"]]
    assert ranks == sorted(ranks)
    assert min(ranks) == 1


def test_team_with_no_fixtures_shows_as_blank(bootstrap, fixtures):
    result = fixture_ticker(bootstrap, fixtures, from_gw=1, num_gws=6)
    tot = next(c for c in result["clubs"] if c["team_short"] == "TOT")
    assert tot["mean_difficulty"] is None
    assert set(tot["blank_gws"]) == {1, 2, 3, 4, 5, 6}
