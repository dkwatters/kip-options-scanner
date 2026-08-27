from dataclasses import replace
from datetime import date
import json
import sqlite3

import pytest

from src.model_performance import model_performance_scorecard, signal_family_summary
from src.research_repository import REPOSITORY_BACKEND_SQLITE, ResearchRepositoryTarget
from src.signal_outcomes import (
    OutcomeFamily, OutcomeStatus, PriceObservation, SignalOutcome,
    compatible_outcome_family, evaluate_signal_outcome,
)
from src.signal_repository import HistoricalSignalConflict, POSTGRES_SCHEMA, SignalRepository
from src.signals import (
    Signal, SignalDirection, SignalFamily, technical_setup_signal,
    volatility_family_smoke_signal,
)


def directional(**overrides):
    values = dict(
        signal_id="directional-1", ticker="SPY", as_of="2026-01-05",
        model_id="model", model_version="v1", direction=SignalDirection.BULLISH,
        conviction=.5, reasoning="directional evidence", created_at="2026-01-05",
    )
    values.update(overrides)
    return Signal(**values)


def volatility(**overrides):
    values = dict(
        signal_id="volatility-1", ticker="SPY", as_of="2026-01-05",
        model_id="volatility-family-smoke", model_version="0.1",
        signal_family=SignalFamily.VOLATILITY,
        direction=SignalDirection.NOT_APPLICABLE, conviction=0.0,
        reasoning="observed volatility context", created_at="2026-01-05",
    )
    values.update(overrides)
    return Signal(**values)


def target(tmp_path):
    return ResearchRepositoryTarget(
        REPOSITORY_BACKEND_SQLITE, sqlite_path=tmp_path / "research.sqlite"
    )


def test_family_specific_direction_validation_preserves_v01_semantics():
    assert directional().signal_family is SignalFamily.DIRECTIONAL
    assert volatility().direction is SignalDirection.NOT_APPLICABLE
    with pytest.raises(ValueError, match="not_applicable"):
        volatility(direction=SignalDirection.NEUTRAL)
    with pytest.raises(ValueError, match="directional semantics"):
        directional(direction=SignalDirection.NOT_APPLICABLE, conviction=0.0)
    with pytest.raises(ValueError, match="zero conviction"):
        volatility(conviction=.2)


def test_technical_setup_contract_and_identity_are_unchanged():
    row = {
        "ticker": "NVDA", "technical_timestamp": "2026-01-05", "scan_id": "scan-1",
        "trend_state": "constructive", "volatility_state": "moderate",
        "price_vs_sma_20": .1,
    }
    signal = technical_setup_signal(row)
    assert signal.signal_family is SignalFamily.DIRECTIONAL
    assert signal.model_version == "technical-setup-signal-v0.1.1"
    assert signal.direction is SignalDirection.BULLISH
    assert signal.conviction == .5


def test_volatility_smoke_producer_is_deterministic_and_observation_only():
    row = {
        "ticker": "nvda", "technical_timestamp": "2026-01-05T16:00:00-05:00",
        "scan_id": "scan-1", "volatility_state": "high",
        "future_volatility_state": "low",
    }
    first = volatility_family_smoke_signal(row)
    second = volatility_family_smoke_signal(row)
    assert first == second
    assert first.signal_family is SignalFamily.VOLATILITY
    assert first.direction is SignalDirection.NOT_APPLICABLE
    assert first.components == {"volatility_state": "high"}
    assert "future_volatility_state" not in first.components
    assert first.metadata["experimental"] is True


def test_family_persistence_round_trip_filter_and_immutability(tmp_path):
    repository = SignalRepository(target(tmp_path))
    rows = (directional(), volatility())
    assert repository.save_signals(rows) == (True, True)
    assert repository.list_signals(signal_family="volatility") == (rows[1],)
    assert repository.save_signal(rows[1]) is False
    with pytest.raises(HistoricalSignalConflict):
        repository.save_signal(replace(rows[1], components={"volatility_state": "high"}))


def test_v01_sqlite_database_bootstraps_family_defaults(tmp_path):
    database = tmp_path / "research.sqlite"
    with sqlite3.connect(database) as connection:
        connection.executescript("""
        CREATE TABLE research_signals (
          signal_id TEXT PRIMARY KEY, ticker TEXT NOT NULL, as_of TEXT NOT NULL,
          model_id TEXT NOT NULL, model_version TEXT NOT NULL, direction TEXT NOT NULL,
          conviction REAL NOT NULL, confidence REAL, reasoning TEXT NOT NULL,
          components TEXT NOT NULL, metadata TEXT NOT NULL, evidence_refs TEXT NOT NULL,
          created_at TEXT NOT NULL);
        CREATE TABLE signal_outcomes (
          signal_id TEXT NOT NULL, horizon_trading_days INTEGER NOT NULL,
          start_date TEXT, end_date TEXT, start_price REAL, end_price REAL,
          absolute_return REAL, directional_correct INTEGER, status TEXT NOT NULL,
          error TEXT, evaluated_at TEXT NOT NULL,
          PRIMARY KEY(signal_id, horizon_trading_days),
          FOREIGN KEY(signal_id) REFERENCES research_signals(signal_id));
        """)
        connection.execute(
            "INSERT INTO research_signals VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            ("legacy", "SPY", "2026-01-05", "model", "v1", "neutral", 0.0,
             None, "legacy", "{}", "{}", json.dumps([]), "2026-01-05"),
        )
        connection.execute(
            "INSERT INTO signal_outcomes VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            ("legacy", 5, "2026-01-05", "2026-01-12", 100, 101, .01, None,
             "evaluated", None, "2026-01-12"),
        )
    repository = SignalRepository(
        ResearchRepositoryTarget(REPOSITORY_BACKEND_SQLITE, sqlite_path=database)
    )
    assert repository.list_signals()[0].signal_family is SignalFamily.DIRECTIONAL
    assert repository.list_outcomes()[0].outcome_family is OutcomeFamily.RETURN


def test_outcome_routing_is_explicit_and_incompatible_families_are_rejected(tmp_path):
    assert compatible_outcome_family(directional()) is OutcomeFamily.RETURN
    assert compatible_outcome_family(volatility()) is OutcomeFamily.VOLATILITY
    with pytest.raises(ValueError, match="directional signal"):
        evaluate_signal_outcome(
            volatility(), [PriceObservation(date(2026, 1, 5), 100)], 5
        )
    repository = SignalRepository(target(tmp_path))
    repository.save_signal(volatility())
    return_outcome = SignalOutcome(
        "volatility-1", 5, OutcomeStatus.EVALUATED,
        absolute_return=.1, directional_correct=True, evaluated_at="2026-02-01",
    )
    with pytest.raises(ValueError, match="volatility signals require volatility outcomes"):
        repository.save_outcomes([return_outcome])
    valid = SignalOutcome(
        "volatility-1", 5, OutcomeStatus.EVALUATED,
        evaluated_at="2026-02-01", outcome_family=OutcomeFamily.VOLATILITY,
        components={"realized_volatility": .24},
    )
    repository.save_outcomes([valid])
    assert repository.list_outcomes() == (valid,)
    with pytest.raises(ValueError, match="directional correctness"):
        replace(valid, directional_correct=True)


def test_directional_scorecard_excludes_volatility_family():
    directional_signal = directional()
    volatility_signal = volatility(model_id="model", model_version="v1")
    result = model_performance_scorecard(
        [directional_signal, volatility_signal], [], model_id="model", model_version="v1"
    )
    assert result["signal_count"] == 1
    assert result["direction_counts"] == {
        "bullish": 1, "neutral": 0, "bearish": 0, "abstain": 0,
    }
    assert result["horizons"][5]["no_outcome_record_count"] == 1
    assert signal_family_summary([directional_signal, volatility_signal]) == {
        "directional": 1, "volatility": 1,
    }


def test_postgres_schema_adds_compatible_family_defaults():
    schema = "\n".join(POSTGRES_SCHEMA)
    assert "signal_family TEXT NOT NULL DEFAULT 'directional'" in schema
    assert "outcome_family TEXT NOT NULL DEFAULT 'return'" in schema
    assert "ADD COLUMN IF NOT EXISTS signal_family" in schema
    assert "ADD COLUMN IF NOT EXISTS outcome_family" in schema
    assert "components TEXT NOT NULL DEFAULT '{}'" in schema
