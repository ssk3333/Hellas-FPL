from insights.differentials import differentials


def test_low_ownership_only(bootstrap, fixtures):
    result = differentials(bootstrap, fixtures, from_gw=1, num_gws=6, ownership_max=10.0, min_minutes=180)
    assert result
    for d in result:
        assert d["ownership_pct"] < 10.0


def test_strong_underlying_player_surfaces(bootstrap, fixtures):
    result = differentials(bootstrap, fixtures, from_gw=1, num_gws=6, ownership_max=10.0, min_minutes=180)
    names = [d["name"] for d in result]
    assert "Palmer" in names
