from datetime import date
from pathlib import Path

from streamlit.testing.v1 import AppTest

from src.research_repository import REPOSITORY_BACKEND_SQLITE, ResearchRepositoryTarget
from src.signal_outcomes import PriceObservation, evaluate_signal_outcome
from src.signal_repository import SignalRepository
from src.signals import Signal, SignalDirection, SignalFamily


def test_model_lab_renders_persisted_outcome_ledger(monkeypatch, tmp_path):
    database = tmp_path / "model-lab.sqlite"
    monkeypatch.setenv("RESEARCH_REPOSITORY_BACKEND", REPOSITORY_BACKEND_SQLITE)
    monkeypatch.setenv("RESEARCH_SQLITE_PATH", str(database))
    repository = SignalRepository(
        ResearchRepositoryTarget(REPOSITORY_BACKEND_SQLITE, sqlite_path=database)
    )
    signal = Signal(
        "signal-1", "SPY", "2026-01-05T12:00:00-05:00", "model", "v1",
        SignalDirection.BULLISH, 0.5, "Existing evidence.",
        created_at="2026-01-05T12:00:00-05:00",
    )
    observations = [
        PriceObservation(date(2026, 1, 5), 100),
        PriceObservation(date(2026, 1, 6), 101),
        PriceObservation(date(2026, 1, 7), 102),
        PriceObservation(date(2026, 1, 8), 103),
        PriceObservation(date(2026, 1, 9), 104),
        PriceObservation(date(2026, 1, 12), 105),
    ]
    repository.save_signal(signal)
    repository.save_outcomes([evaluate_signal_outcome(signal, observations, 5)])

    app = AppTest.from_file(Path(__file__).parents[1] / "app.py", default_timeout=20).run()
    next(widget for widget in app.sidebar.radio if widget.label == "Navigation").set_value(
        "Model Lab"
    )
    app.run()

    assert not app.exception
    assert [title.value for title in app.title] == ["Model Lab"]
    frames = [element.value for element in app.dataframe]
    outcome_frame = next(frame for frame in frames if "Forward return" in frame.columns)
    assert outcome_frame.iloc[0]["Status"] == "evaluated"
    assert outcome_frame.iloc[0]["End date"] == "2026-01-12"


def test_model_lab_groups_volatility_without_direction_tiles(monkeypatch, tmp_path):
    database = tmp_path / "typed-model-lab.sqlite"
    monkeypatch.setenv("RESEARCH_REPOSITORY_BACKEND", REPOSITORY_BACKEND_SQLITE)
    monkeypatch.setenv("RESEARCH_SQLITE_PATH", str(database))
    repository = SignalRepository(
        ResearchRepositoryTarget(REPOSITORY_BACKEND_SQLITE, sqlite_path=database)
    )
    repository.save_signals((
        Signal(
            "directional", "SPY", "2026-01-05", "shared", "v1",
            SignalDirection.BULLISH, .5, "directional", created_at="2026-01-05",
        ),
        Signal(
            "volatility", "SPY", "2026-01-05", "volatility-family-smoke", "0.1",
            SignalDirection.NOT_APPLICABLE, 0.0, "experimental",
            signal_family=SignalFamily.VOLATILITY,
            components={"volatility_state": "high"}, created_at="2026-01-05",
        ),
    ))
    app = AppTest.from_file(Path(__file__).parents[1] / "app.py", default_timeout=20).run()
    next(widget for widget in app.sidebar.radio if widget.label == "Navigation").set_value("Model Lab")
    app.run()
    family = next(widget for widget in app.selectbox if widget.label == "Signal family")
    family.set_value(SignalFamily.VOLATILITY)
    app.run()
    assert not app.exception
    assert [metric.label for metric in app.metric] == ["Volatility Signals"]
    ledger = next(frame.value for frame in app.dataframe if "Signal family" in frame.value.columns)
    assert ledger.iloc[0]["Signal family"] == "volatility"
    assert ledger.iloc[0]["Direction"] == "N/A"
    assert any("No volatility outcome metrics" in row.value for row in app.info)
