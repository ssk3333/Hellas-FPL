from insights.underlying import form_vs_underlying


def test_overperformer_and_underperformer(bootstrap):
    result = form_vs_underlying(bootstrap, min_minutes=180)
    over_names = [p["name"] for p in result["overperformers"]]
    under_names = [p["name"] for p in result["underperformers"]]
    assert "Haaland" in over_names  # goals+assists well above xGI
    assert "Havertz" in under_names  # xGI well above actual output


def test_defenders_keepers_ranked_by_xgc(bootstrap):
    result = form_vs_underlying(bootstrap, min_minutes=180)
    xgc_values = [p["xgc_per_90"] for p in result["defenders_keepers"]]
    assert xgc_values == sorted(xgc_values)
