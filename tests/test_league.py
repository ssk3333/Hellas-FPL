from insights.league import league_intelligence


def test_rank_and_gap(bootstrap, standings, rival_picks):
    result = league_intelligence(standings, bootstrap, my_team_id=639054, rival_picks_by_entry=rival_picks)
    assert result["available"] is True
    assert result["my_rank"] == 3
    assert result["gap_to_leader"] == 20


def test_movers_and_rival_captains(bootstrap, standings, rival_picks):
    result = league_intelligence(standings, bootstrap, my_team_id=639054, rival_picks_by_entry=rival_picks)
    up_names = [m["manager"] for m in result["biggest_movers_up"]]
    assert "Test Manager" in up_names  # rank 5 -> 3

    rival_111 = next(r for r in result["top_rivals"] if r["entry"] == 111)
    assert rival_111["captain"] == "Haaland"
    assert rival_111["captain_is_template"] is True

    rival_222 = next(r for r in result["top_rivals"] if r["entry"] == 222)
    assert rival_222["captain"] == "Palmer"
    assert rival_222["captain_is_template"] is False


def test_no_standings():
    result = league_intelligence(None, {}, my_team_id=639054)
    assert result["available"] is False
