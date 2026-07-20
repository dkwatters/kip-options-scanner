import inspect

from src.universe_analysis import (
    analysis_summary,
    PRESENTATION_EXTENSION_THRESHOLDS,
    analysis_explanation,
    extension_profile,
    filter_analysis_rows,
    ranked_analysis_rows,
)


def _row(ticker, *, p20=.01, p50=.02, p200=.03, trend="mixed", momentum="neutral", volatility="moderate", rsi=50, macd=.1):
    return {
        "ticker": ticker, "scan_id": "exact-run", "technical_timestamp": "July 20, 2026",
        "price": 100.0, "sma_20": 95.0, "sma_50": 90.0, "sma_200": 80.0,
        "price_vs_sma_20": p20, "price_vs_sma_50": p50, "price_vs_sma_200": p200,
        "sma_20_vs_sma_50": .05, "sma_50_vs_sma_200": .10,
        "rsi_14": rsi, "macd_line": 1.0, "macd_signal": .5,
        "macd_histogram": macd, "realized_volatility_20d": .35,
        "trend_state": trend, "momentum_state": momentum,
        "volatility_state": volatility, "technical_score": 42.0,
        "technical_notes": "raw notes",
    }


def test_crwd_style_profile_can_be_strong_bullish_positive_and_extended():
    crwd = _row("CRWD", p20=.091, p50=.21, p200=.539, trend="bullish_alignment", momentum="positive", rsi=67)
    ranked = ranked_analysis_rows([crwd])
    assert ranked[0]["technical_profile"] == "Strong"
    assert ranked[0]["trend_label"] == "Bullish alignment"
    assert ranked[0]["momentum_label"] == "Positive"
    assert ranked[0]["extension_label"] == "Elevated"
    assert ranked[0]["technical_score"] == 42.0


def test_positive_sma_distance_is_not_automatically_unqualified_good():
    assert extension_profile(_row("CRWD", p20=.091, p50=.21, p200=.539)) == "Elevated"
    assert PRESENTATION_EXTENSION_THRESHOLDS.elevated_20 == .08


def test_rank_uses_existing_score_and_ticker_tie_break_without_membership_change():
    rows = [_row("ZS", trend="mixed"), _row("PANW", trend="bullish_alignment", momentum="positive"), _row("CRWD", trend="bullish_alignment", momentum="positive")]
    before = {row["ticker"] for row in rows}
    ranked = ranked_analysis_rows(rows)
    assert [row["ticker"] for row in ranked] == ["CRWD", "PANW", "ZS"]
    assert [row["rank"] for row in ranked] == [1, 2, 3]
    assert {row["ticker"] for row in ranked} == before


def test_filters_change_display_only_and_reset_population_is_preserved():
    ranked = ranked_analysis_rows([_row("CRWD", trend="bullish_alignment", momentum="positive"), _row("ZS", trend="mixed")])
    visible = filter_analysis_rows(ranked, trends=("Bullish alignment",))
    assert [row["ticker"] for row in visible] == ["CRWD"]
    assert len(ranked) == 2
    assert len(filter_analysis_rows(ranked)) == 2


def test_expanded_explanation_is_deterministic_complete_and_has_no_ai():
    row = ranked_analysis_rows([_row("CRWD", p20=.091, p50=.21, p200=.539, trend="bullish_alignment", momentum="positive", rsi=67)])[0]
    first = analysis_explanation(row)
    assert first == analysis_explanation(row)
    text = " ".join((first["summary"], *first["positives"], *first["watchouts"])).lower()
    for concept in ("moving average", "macd", "momentum", "trend", "entry timing"):
        assert concept in text
    page_source = open("src/universe_analysis_page.py", encoding="utf-8").read().lower()
    for factor in ("20-day sma", "50-day sma", "200-day sma", "rsi", "macd", "trend", "momentum", "extension", "volatility", "observation timestamp"):
        assert factor in page_source
    assert "openai" not in inspect.getsource(analysis_explanation).lower()


def test_primary_page_demotes_raw_score_and_requires_exact_run():
    source = open("src/universe_analysis_page.py", encoding="utf-8").read()
    table = source[source.index("comparison ="):source.index("styled_comparison =")]
    assert '"Technical Profile"' in table
    assert '"Technical Profile Score"' not in table
    assert "No exact Research Universe analysis run is selected" in source
    assert "stored observations do not reconcile" in source
    assert "Current exact run/scan ID" in source
    assert "_semantic_color" in source


def test_company_handoff_retains_exact_parent_and_run_context():
    source = open("src/universe_analysis_page.py", encoding="utf-8").read()
    for field in ("company_name", "parent_universe_id", "parent_universe_version", "parent_universe_title", "analysis_run_reference", "observation_timestamp", "return_destination"):
        assert f'"{field}"' in source


def test_summary_counts_reconcile_exactly():
    ranked = ranked_analysis_rows([
        _row("CRWD", trend="bullish_alignment", momentum="positive"),
        _row("ZS", trend="mixed", momentum="neutral", rsi=49),
    ])
    summary = analysis_summary(ranked)
    assert sum(summary["profiles"].values()) == summary["analyzed"] == 2
    assert summary["bullish_trends"] == 1
    assert summary["above_200_day_sma"] == 2
    assert summary["average_rsi"] == 49.5


def test_mixed_trend_explanation_does_not_claim_strong_alignment():
    row = ranked_analysis_rows([_row("ZS", p20=.09, trend="mixed")])[0]
    explanation = analysis_explanation(row)
    text = " ".join((explanation["summary"], *explanation["positives"])).lower()
    assert "strong trend alignment" not in text
    assert "bullish moving-average alignment" not in text
