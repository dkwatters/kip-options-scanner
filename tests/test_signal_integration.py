from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from streamlit.testing.v1 import AppTest

import app as streamlit_app
from src.research_repository import (
    REPOSITORY_BACKEND_SQLITE,
    ResearchRepositoryTarget,
    research_repository_from_target,
)
from src.research_universe import ResearchUniverseReviewService, UniverseSource, source_record
from src.research_universe_analysis import execute_research_universe_analysis, preflight_research_universe
from src.signal_repository import HistoricalSignalConflict, SignalRepository
from src.signals import technical_setup_signal
from src.technical_observation_service import archive_technical_observations_and_signals, safe_diagnostic_detail
from tests.test_research_universe_analysis import FakeMarketData


NOW = datetime(2026, 7, 20, 12, 0, tzinfo=ZoneInfo("America/New_York"))


def _target(tmp_path):
    return ResearchRepositoryTarget(REPOSITORY_BACKEND_SQLITE, sqlite_path=tmp_path / "research.sqlite")


def _row(scan_id="same-scan", ticker="NVDA"):
    return {
        "scan_id": scan_id, "ticker": ticker,
        "technical_timestamp": "2026-07-20 12:00:00 PM EDT",
        "trend_state": "bullish_alignment", "momentum_state": "positive",
        "volatility_state": "moderate", "price": 125.0,
        "price_vs_sma_20": .1, "price_vs_sma_50": .1, "price_vs_sma_200": .1,
        "sma_20_vs_sma_50": .1, "sma_50_vs_sma_200": .1,
        "rsi_14": 60.0, "macd_line": 2.0, "macd_signal": 1.0,
        "macd_histogram": 1.0,
    }


def test_universe_analysis_archives_observation_and_signal_visible_in_model_lab(monkeypatch, tmp_path):
    target = _target(tmp_path)
    repository = research_repository_from_target(target)
    signal_repository = SignalRepository(target)
    universe = ResearchUniverseReviewService().assemble(
        universe_id="nvda", title="NVDA research",
        starting_companies=(source_record(
            {"company_name": "NVIDIA", "ticker": "NVDA", "identity_status": "resolved"},
            UniverseSource.USER_ENTERED,
        ),),
    )
    client = FakeMarketData()
    run = execute_research_universe_analysis(
        preflight_research_universe(universe.downstream_handoff(), client),
        client=client, repository=repository, signal_repository=signal_repository, now=NOW,
    )
    assert run.signal_persistence_error is None
    assert repository.technical_analysis_observations(scan_id=run.scan_id)["rows"][0]["ticker"] == "NVDA"
    persisted = signal_repository.list_signals(ticker="NVDA")
    assert {(signal.model_id, signal.model_version) for signal in persisted} == {
        ("technical-setup-score", "technical-setup-signal-v0.1.1"),
        ("volatility-context", "volatility-context-v0.1"),
    }

    monkeypatch.setenv("RESEARCH_REPOSITORY_BACKEND", REPOSITORY_BACKEND_SQLITE)
    monkeypatch.setenv("RESEARCH_SQLITE_PATH", str(target.sqlite_path))
    model_lab = AppTest.from_file(Path(__file__).parents[1] / "app.py", default_timeout=20).run()
    next(widget for widget in model_lab.sidebar.radio if widget.label == "Navigation").set_value("Model Lab")
    model_lab.run()
    assert not model_lab.exception
    ledger = next(frame.value for frame in model_lab.dataframe if "Signal ID" in frame.value.columns)
    assert ledger.iloc[0]["Security"] == "NVDA"


def test_opportunity_archival_still_derives_signal(monkeypatch, tmp_path):
    target = _target(tmp_path)
    monkeypatch.setenv("RESEARCH_REPOSITORY_BACKEND", REPOSITORY_BACKEND_SQLITE)
    monkeypatch.setenv("RESEARCH_SQLITE_PATH", str(target.sqlite_path))
    monkeypatch.setattr(streamlit_app, "TradierClient", lambda: object())
    monkeypatch.setattr(streamlit_app, "technical_analysis_rows_for_symbols", lambda *args, **kwargs: ([_row("opportunity-1")], {}))
    result = streamlit_app.archive_current_opportunity_scan(
        [], "opportunity-1", _row()["technical_timestamp"], "test", "Both", 14, 45,
        ["NVDA"], {"study_id": "SP-001", "study_name": "test", "study_version": "1", "study_purpose": "test", "scheduled_time_label": None, "run_mode": "manual-ui"},
    )
    assert result.signals_persisted
    assert SignalRepository(target).list_signals(ticker="NVDA")[0].model_version == "technical-setup-signal-v0.1.1"


def test_shared_boundary_is_idempotent_and_conflict_batch_is_atomic(tmp_path):
    target = _target(tmp_path)
    research = research_repository_from_target(target)
    signals = SignalRepository(target)
    kwargs = dict(
        archive_observations=lambda rows: research.archive_technical_observations(
            scan_id="same-scan", technical_rows=rows,
            study_protocol={"study_id": "TAM-001", "study_name": "test", "study_version": "1", "study_purpose": "test", "scheduled_time_label": None, "run_mode": "manual-ui"},
        ), signal_repository=signals,
    )
    first = archive_technical_observations_and_signals([_row()], **kwargs)
    retry = archive_technical_observations_and_signals([_row()], **kwargs)
    assert first.signal_inserted_count == 1 and retry.signal_retry_count == 1
    assert len(signals.list_signals()) == 1

    existing = signals.list_signals()[0]
    conflicting = technical_setup_signal({**_row(), "trend_state": "bearish_alignment"})
    assert conflicting.signal_id == existing.signal_id
    result = archive_technical_observations_and_signals(
        [{**_row("new-scan", "AAPL")}, {**_row(), "trend_state": "bearish_alignment"}],
        archive_observations=lambda rows: len(rows), signal_repository=signals,
    )
    assert "HistoricalSignalConflict" in result.signal_persistence_error
    assert {signal.ticker for signal in signals.list_signals()} == {"NVDA"}


def test_signal_failure_is_visible_and_missing_tam_does_not_report_signal_success(monkeypatch, tmp_path):
    app = AppTest.from_string('''
from src.signal_status_ui import render_signal_persistence_failure
render_signal_persistence_failure("HistoricalSignalConflict: immutable content")
''').run()
    assert "Analysis archived, but derived Signals were not persisted." in app.warning[0].value

    monkeypatch.setattr(streamlit_app, "TradierClient", lambda: object())
    monkeypatch.setattr(streamlit_app, "technical_analysis_rows_for_symbols", lambda *args, **kwargs: ([], {"NVDA": "provider unavailable"}))
    try:
        streamlit_app.archive_current_opportunity_scan(
            [], "failed", _row()["technical_timestamp"], "test", "Both", 14, 45, ["NVDA"], {},
        )
    except RuntimeError as error:
        assert "Required technical analysis did not produce any observations" in str(error)
    else:
        raise AssertionError("missing TAM data was reported as successful")

    empty = archive_technical_observations_and_signals(
        [], archive_observations=lambda rows: {"technical_characterization": 0},
        signal_repository=SignalRepository(_target(tmp_path)),
    )
    assert not empty.signals_persisted
    assert "No successfully generated technical observations" in empty.signal_persistence_error
    assert "secret" not in safe_diagnostic_detail(
        RuntimeError("postgresql://user:secret@database.example/research failed")
    )
