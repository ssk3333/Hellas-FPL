from insights.availability import availability_risk


def test_flags_injured_and_doubtful(bootstrap):
    result = availability_risk(bootstrap)
    names = {p["name"] for p in result}
    assert "Colwill" in names
    assert "De Bruyne" in names
    assert "Haaland" not in names


def test_restricts_to_player_ids(bootstrap):
    result = availability_risk(bootstrap, player_ids=[16])
    assert len(result) == 1
    assert result[0]["name"] == "Colwill"
