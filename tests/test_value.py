from insights.value import value_tables


def test_value_positions_present(bootstrap):
    result = value_tables(bootstrap, min_minutes=180)
    assert set(result.keys()) == {"GKP", "DEF", "MID", "FWD"}
    assert len(result["MID"]) > 0


def test_cheap_high_scorer_tops_value_table(bootstrap):
    result = value_tables(bootstrap, min_minutes=180)
    assert result["MID"][0]["name"] == "Palmer"
