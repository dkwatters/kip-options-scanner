from streamlit.testing.v1 import AppTest


APP = r'''
from types import SimpleNamespace
import streamlit as st
import src.universe_analysis_page as page
from src.research_universe import IdentityStatus
from src.research_universe_analysis import AnalysisLedgerEntry, AnalysisMemberStatus

def row(ticker, p20, p50, p200, trend, momentum, rsi):
    return {
        "ticker": ticker, "scan_id": "exact-cyber", "technical_timestamp": "2026-07-20 12:00 EDT",
        "price": 100.0, "sma_20": 95.0, "sma_50": 90.0, "sma_200": 80.0,
        "price_vs_sma_20": p20, "price_vs_sma_50": p50, "price_vs_sma_200": p200,
        "sma_20_vs_sma_50": .05, "sma_50_vs_sma_200": .1, "rsi_14": rsi,
        "macd_line": 1.0, "macd_signal": .5, "macd_histogram": .5,
        "realized_volatility_20d": .35, "trend_state": trend,
        "momentum_state": momentum, "volatility_state": "moderate",
        "technical_score": 77.0, "technical_notes": "raw diagnostic notes",
    }

ROWS = [
    row("CRWD", .091, .21, .539, "bullish_alignment", "positive", 67),
    row("PANW", .03, .07, .12, "constructive", "positive", 61),
    row("ZS", -.02, .01, .02, "mixed", "neutral", 49),
]

class Repo:
    def technical_analysis_observations(self, **kwargs):
        if kwargs.get("scan_id") == "exact-cyber":
            return {"rows": tuple(ROWS), "available_scan_ids": ("exact-cyber", "legacy-66")}
        if kwargs.get("scan_id") == "legacy-66":
            return {"rows": ({"ticker": "LEGACY"},), "available_scan_ids": ("exact-cyber", "legacy-66")}
        return {"rows": (), "available_scan_ids": ("exact-cyber", "legacy-66")}

page.research_repository_from_env = lambda: Repo()
if "active_universe_analysis_run" not in st.session_state:
    st.session_state.active_universe_analysis_handoff = SimpleNamespace(
        universe_id="cyber", universe_version=3, universe_title="Cybersecurity",
    )
    ledger = tuple(
        AnalysisLedgerEntry("ticker:" + ticker, name, ticker, IdentityStatus.RESOLVED, AnalysisMemberStatus.ANALYZED, "Completed")
        for ticker, name in (("CRWD", "CrowdStrike"), ("PANW", "Palo Alto Networks"), ("ZS", "Zscaler"))
    ) + (AnalysisLedgerEntry("ticker:BAD", "Unsupported Co", "BAD-AI", IdentityStatus.RESOLVED, AnalysisMemberStatus.UNSUPPORTED, "Unsupported identifier"),)
    st.session_state.active_universe_analysis_run = SimpleNamespace(
        universe_id="cyber", universe_version=3, universe_title="Cybersecurity",
        research_question="Which companies protect AI-forward enterprises?",
        requested_constituent_count=4, analyzed_tickers=("CRWD", "PANW", "ZS"),
        timestamp="July 20, 2026", scan_id="exact-cyber", ledger=ledger,
    )
page.render_universe_analysis()
'''


def _comparison(app):
    return next(frame.value for frame in app.dataframe if "Technical Profile" in frame.value.columns)


def _select_company_row(app, index):
    key = "universe_company_comparison_cyber:v3:exact-cyber"
    app.session_state[key] = {"selection": {"rows": [index], "columns": [], "cells": []}}
    return app.run()


def _deselect_company_row(app):
    key = "universe_company_comparison_cyber:v3:exact-cyber"
    app.session_state[key] = {"selection": {"rows": [], "columns": [], "cells": []}}
    return app.run()


def test_primary_page_accounts_for_exact_population_and_demotes_score():
    app = AppTest.from_string(APP).run()
    assert not app.exception
    assert app.title[0].value == "Cybersecurity"
    table = _comparison(app)
    assert list(table["Ticker"]) == ["CRWD", "PANW", "ZS"]
    assert list(table["Rank"]) == [1, 2, 3]
    assert "Technical Profile Score" not in table.columns
    unavailable = next(frame.value for frame in app.dataframe if "BAD-AI" in frame.value.astype(str).to_string())
    assert unavailable.iloc[0]["Status"] == "unsupported identifier"
    assert any("4 universe members" in caption.value and "3 analyzed" in caption.value for caption in app.caption)
    assert not any("scan ID" in title.value for title in app.title)


def test_filters_change_display_not_total_and_reset_restores_rows():
    app = AppTest.from_string(APP).run()
    next(widget for widget in app.multiselect if widget.label == "Trend").set_value(["Bullish alignment"])
    app.run()
    assert list(_comparison(app)["Ticker"]) == ["CRWD"]
    run = app.session_state["active_universe_analysis_run"]
    assert run.requested_constituent_count == 4
    next(button for button in app.button if button.label == "Reset filters").click()
    app.run()
    assert len(_comparison(app)) == 3


def test_detail_and_company_handoff_retain_parent_context():
    app = AppTest.from_string(APP).run()
    assert not any(select.label == "View details" for select in app.selectbox)
    _select_company_row(app, 0)
    factor_table = next(frame.value for frame in app.dataframe if "Factor" in frame.value.columns)
    assert {"20-day SMA", "50-day SMA", "200-day SMA", "RSI", "MACD histogram", "Trend", "Momentum", "Extension", "Volatility", "Technical Profile Score"}.issubset(set(factor_table["Factor"]))
    assert factor_table.loc[factor_table["Factor"] == "Extension", "Value"].iloc[0] == "Elevated"
    assert factor_table.loc[factor_table["Factor"] == "Price", "Value"].iloc[0] == "$100.00"
    assert factor_table.loc[factor_table["Factor"] == "RSI", "Value"].iloc[0] == "67.00"
    assert factor_table.loc[factor_table["Factor"] == "MACD histogram", "Value"].iloc[0] == "0.50"
    assert factor_table.loc[factor_table["Factor"] == "Price vs. 20-day SMA", "Value"].iloc[0] == "+9.1%"
    assert {"Trend & Position", "Momentum", "Risk / Positioning"}.issubset(set(factor_table["Group"]))
    next(button for button in app.button if button.label == "View Company Analysis").click()
    _select_company_row(app, 0)
    context = app.session_state["company_analysis_context"]
    assert context["ticker"] == "CRWD"
    assert context["company_name"] == "CrowdStrike"
    assert context["parent_universe_id"] == "cyber"
    assert context["analysis_run_reference"] == "exact-cyber"
    assert context["return_destination"] == "Universe Analysis"


def test_table_selection_updates_detail_and_is_scoped_to_run():
    app = AppTest.from_string(APP).run()
    _select_company_row(app, 0)
    assert app.session_state["universe_analysis_active_company"]["ticker"] == "CRWD"
    assert any(metric.label == "Current Technical Profile" for metric in app.metric)
    assert any("Rank #1 of 3 analyzed" in item.value for item in app.markdown)
    assert not any("Why this profile?" in expander.label for expander in app.expander)

    _select_company_row(app, 2)
    assert app.session_state["universe_analysis_active_company"]["ticker"] == "ZS"
    assert any("Rank #3 of 3 analyzed" in item.value for item in app.markdown)
    assert not any("Rank #1 of 3 analyzed" in item.value for item in app.markdown)
    selected_rows = app.session_state["universe_company_comparison_cyber:v3:exact-cyber"]["selection"]["rows"]
    assert selected_rows == [2]

    app.session_state["active_universe_analysis_run"].scan_id = "another-run"
    app.run()
    assert "universe_analysis_active_company" not in app.session_state


def test_deselecting_active_company_removes_detail():
    app = AppTest.from_string(APP).run()
    _select_company_row(app, 0)
    assert any(metric.label == "Current Technical Profile" for metric in app.metric)

    _deselect_company_row(app)
    assert "universe_analysis_active_company" not in app.session_state
    assert not any(metric.label == "Current Technical Profile" for metric in app.metric)
    assert not any(frame.value.columns.tolist() == ["Group", "Factor", "Value", "Interpretation"] for frame in app.dataframe)


def test_filter_removing_selected_row_clears_detail_deterministically():
    app = AppTest.from_string(APP).run()
    _select_company_row(app, 0)
    next(widget for widget in app.multiselect if widget.label == "Trend").set_value(["Mixed"])
    app.run()
    assert "universe_analysis_active_company" not in app.session_state
    assert not any("Why this profile?" in expander.label for expander in app.expander)


def test_diagnostics_retain_raw_data_and_history_is_secondary():
    app = AppTest.from_string(APP).run()
    assert "Technical Data & Diagnostics" in open("src/universe_analysis_page.py", encoding="utf-8").read()
    raw = next(frame.value for frame in app.dataframe if "technical_notes" in frame.value.columns)
    assert set(raw["ticker"]) == {"CRWD", "PANW", "ZS"}
    assert any("Current exact run/scan ID: exact-cyber" in caption.value for caption in app.caption)
    assert any(select.label == "Historical scan ID" for select in app.selectbox)


def test_population_charts_are_in_optional_collapsed_distribution_section():
    app = AppTest.from_string(APP).run()
    source = open("src/universe_analysis_page.py", encoding="utf-8").read()
    assert 'st.expander("Universe distribution", expanded=False' in source
    assert any("Technical Profile Distribution" in item.value for item in app.markdown)


def test_archived_analysis_surfaces_derived_signal_persistence_failure():
    app = AppTest.from_string(APP).run()
    app.session_state["active_universe_analysis_run"].signal_persistence_error = (
        "HistoricalSignalConflict: immutable content"
    )
    app.run()
    assert any(
        "Analysis archived, but derived Signals were not persisted." in warning.value
        for warning in app.warning
    )


def test_investor_copy_omits_removed_implementation_language():
    source = open("src/universe_analysis_page.py", encoding="utf-8").read()
    assert "presentation rules" not in source
    assert 'st.selectbox("View details"' not in source
