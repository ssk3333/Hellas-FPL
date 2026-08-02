from insights.trend import season_trend


def test_season_trend_totals(history):
    result = season_trend(history)
    assert result["available"] is True
    assert len(result["gameweeks"]) == 2
    assert result["total_bench_points_wasted"] == 11  # 8 + 3
    assert result["total_hits_cost"] == 4


def test_no_history():
    result = season_trend(None)
    assert result["available"] is False
