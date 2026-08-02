from insights.captaincy import captaincy_shortlist


def test_shortlist_excludes_flagged_players(bootstrap, fixtures):
    result = captaincy_shortlist(bootstrap, fixtures, from_gw=1, top_n=8)
    names = [c["name"] for c in result["shortlist"]]
    assert "Haaland" in names
    assert "De Bruyne" not in names  # status 'd', doubtful -- excluded outright


def test_safe_and_differential_picks(bootstrap, fixtures):
    result = captaincy_shortlist(bootstrap, fixtures, from_gw=1, top_n=8, differential_ownership_max=10.0)
    assert result["safe_pick"] is not None
    assert result["safe_pick"]["ownership_pct"] >= result["differential_pick"]["ownership_pct"]


def test_excludes_blank_gameweek_teams(bootstrap, fixtures):
    result = captaincy_shortlist(bootstrap, fixtures, from_gw=5, top_n=8)
    names = [c["name"] for c in result["shortlist"]]
    assert "Salah" not in names  # Liverpool blank in gw5
