"""Signal/outcome persistence using the configured Research Repository target."""
from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Iterable

from src.research_repository import (
    DEFAULT_RESEARCH_DB_PATH, REPOSITORY_BACKEND_POSTGRES,
    ResearchRepositoryTarget, research_repository_target_from_env,
)
from src.signal_outcomes import (
    OutcomeFamily, OutcomeStatus, SignalOutcome,
    validate_signal_outcome_compatibility,
)
from src.signals import Signal, SignalDirection, SignalFamily

SIGNAL_COLUMNS = ("signal_id", "ticker", "as_of", "model_id", "model_version", "direction", "conviction", "confidence", "reasoning", "components", "metadata", "evidence_refs", "created_at", "signal_family")
OUTCOME_COLUMNS = ("signal_id", "horizon_trading_days", "start_date", "end_date", "start_price", "end_price", "absolute_return", "directional_correct", "status", "error", "evaluated_at", "outcome_family", "components")

SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS research_signals (
 signal_id TEXT PRIMARY KEY, ticker TEXT NOT NULL, as_of TEXT NOT NULL,
 model_id TEXT NOT NULL, model_version TEXT NOT NULL, direction TEXT NOT NULL,
 conviction REAL NOT NULL, confidence REAL, reasoning TEXT NOT NULL,
 components TEXT NOT NULL, metadata TEXT NOT NULL, evidence_refs TEXT NOT NULL,
 created_at TEXT NOT NULL,
 signal_family TEXT NOT NULL DEFAULT 'directional'
);
CREATE INDEX IF NOT EXISTS idx_research_signals_security_asof ON research_signals(ticker, as_of);
CREATE INDEX IF NOT EXISTS idx_research_signals_model_asof ON research_signals(model_id, model_version, as_of);
CREATE TABLE IF NOT EXISTS signal_outcomes (
 signal_id TEXT NOT NULL, horizon_trading_days INTEGER NOT NULL,
 start_date TEXT, end_date TEXT, start_price REAL, end_price REAL,
 absolute_return REAL, directional_correct INTEGER, status TEXT NOT NULL,
 error TEXT, evaluated_at TEXT NOT NULL,
 outcome_family TEXT NOT NULL DEFAULT 'return',
 components TEXT NOT NULL DEFAULT '{}',
 PRIMARY KEY(signal_id, horizon_trading_days),
 FOREIGN KEY(signal_id) REFERENCES research_signals(signal_id)
);
CREATE INDEX IF NOT EXISTS idx_signal_outcomes_status_horizon ON signal_outcomes(status, horizon_trading_days);
"""

POSTGRES_SCHEMA = tuple(statement.strip() for statement in (
    """CREATE TABLE IF NOT EXISTS research_signals (
     signal_id TEXT PRIMARY KEY, ticker TEXT NOT NULL, as_of TEXT NOT NULL,
     model_id TEXT NOT NULL, model_version TEXT NOT NULL, direction TEXT NOT NULL,
     conviction DOUBLE PRECISION NOT NULL, confidence DOUBLE PRECISION, reasoning TEXT NOT NULL,
     components TEXT NOT NULL, metadata TEXT NOT NULL, evidence_refs TEXT NOT NULL, created_at TEXT NOT NULL,
     signal_family TEXT NOT NULL DEFAULT 'directional')""",
    "ALTER TABLE research_signals ADD COLUMN IF NOT EXISTS signal_family TEXT NOT NULL DEFAULT 'directional'",
    "CREATE INDEX IF NOT EXISTS idx_research_signals_security_asof ON research_signals(ticker, as_of)",
    "CREATE INDEX IF NOT EXISTS idx_research_signals_model_asof ON research_signals(model_id, model_version, as_of)",
    "CREATE INDEX IF NOT EXISTS idx_research_signals_family_asof ON research_signals(signal_family, as_of)",
    """CREATE TABLE IF NOT EXISTS signal_outcomes (
     signal_id TEXT NOT NULL REFERENCES research_signals(signal_id), horizon_trading_days INTEGER NOT NULL,
     start_date TEXT, end_date TEXT, start_price DOUBLE PRECISION, end_price DOUBLE PRECISION,
     absolute_return DOUBLE PRECISION, directional_correct BOOLEAN, status TEXT NOT NULL,
     error TEXT, evaluated_at TEXT NOT NULL, outcome_family TEXT NOT NULL DEFAULT 'return',
     components TEXT NOT NULL DEFAULT '{}',
     PRIMARY KEY(signal_id, horizon_trading_days))""",
    "ALTER TABLE signal_outcomes ADD COLUMN IF NOT EXISTS outcome_family TEXT NOT NULL DEFAULT 'return'",
    "ALTER TABLE signal_outcomes ADD COLUMN IF NOT EXISTS components TEXT NOT NULL DEFAULT '{}'",
    "CREATE INDEX IF NOT EXISTS idx_signal_outcomes_status_horizon ON signal_outcomes(status, horizon_trading_days)",
    "CREATE INDEX IF NOT EXISTS idx_signal_outcomes_family_horizon ON signal_outcomes(outcome_family, horizon_trading_days)",
) if statement)


class HistoricalSignalConflict(ValueError):
    """Raised when a caller attempts to change an existing signal identity."""


class SignalRepository:
    def __init__(self, target: ResearchRepositoryTarget):
        self.target = target

    def _connect(self):
        if self.target.backend == REPOSITORY_BACKEND_POSTGRES:
            import psycopg
            return psycopg.connect(self.target.database_url)
        path = Path(self.target.sqlite_path or DEFAULT_RESEARCH_DB_PATH)
        path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(path)
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def initialize(self) -> None:
        with closing(self._connect()) as connection:
            if self.target.backend == REPOSITORY_BACKEND_POSTGRES:
                with connection.cursor() as cursor:
                    for statement in POSTGRES_SCHEMA:
                        cursor.execute(statement)
            else:
                connection.executescript(SQLITE_SCHEMA)
                _ensure_sqlite_family_columns(connection)
            connection.commit()

    def save_signal(self, signal: Signal) -> bool:
        """Append a signal, accepting an identical retry but rejecting mutation."""
        return self.save_signals((signal,))[0]

    def save_signals(self, signals: Iterable[Signal]) -> tuple[bool, ...]:
        """Persist a batch atomically; any conflict rolls back every new row."""
        self.initialize()
        placeholder = "%s" if self.target.backend == REPOSITORY_BACKEND_POSTGRES else "?"
        with closing(self._connect()) as connection:
            cursor = connection.cursor()
            inserted: list[bool] = []
            try:
                for signal in signals:
                    values = _signal_values(signal)
                    cursor.execute(f"SELECT {', '.join(SIGNAL_COLUMNS)} FROM research_signals WHERE signal_id = {placeholder}", (signal.signal_id,))
                    existing = cursor.fetchone()
                    if existing is not None:
                        if tuple(existing) != values:
                            raise HistoricalSignalConflict(f"Signal {signal.signal_id} already exists with different immutable content.")
                        inserted.append(False)
                        continue
                    cursor.execute(f"INSERT INTO research_signals ({', '.join(SIGNAL_COLUMNS)}) VALUES ({', '.join([placeholder] * len(values))})", values)
                    inserted.append(True)
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return tuple(inserted)

    def list_signals(self, *, ticker: str | None = None, model_id: str | None = None, model_version: str | None = None, signal_family: SignalFamily | str | None = None, as_of_start: str | None = None, as_of_end: str | None = None) -> tuple[Signal, ...]:
        self.initialize()
        placeholder = "%s" if self.target.backend == REPOSITORY_BACKEND_POSTGRES else "?"
        clauses, params = [], []
        family_value = SignalFamily(signal_family).value if signal_family is not None else None
        for column, value, operator in (("ticker", ticker.upper() if ticker else None, "="), ("model_id", model_id, "="), ("model_version", model_version, "="), ("signal_family", family_value, "="), ("as_of", as_of_start, ">="), ("as_of", as_of_end, "<=")):
            if value is not None:
                clauses.append(f"{column} {operator} {placeholder}"); params.append(value)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        with closing(self._connect()) as connection:
            cursor = connection.cursor(); cursor.execute(f"SELECT {', '.join(SIGNAL_COLUMNS)} FROM research_signals{where} ORDER BY as_of DESC, signal_id", tuple(params))
            return tuple(_signal_from_row(row) for row in cursor.fetchall())

    def save_outcomes(self, outcomes: Iterable[SignalOutcome]) -> None:
        self.initialize(); placeholder = "%s" if self.target.backend == REPOSITORY_BACKEND_POSTGRES else "?"
        outcome_rows = tuple(outcomes)
        requested_signal_ids = {outcome.signal_id for outcome in outcome_rows}
        signals_by_id = {
            signal.signal_id: signal for signal in self.list_signals()
            if signal.signal_id in requested_signal_ids
        }
        for outcome in outcome_rows:
            signal = signals_by_id.get(outcome.signal_id)
            if signal is not None:
                validate_signal_outcome_compatibility(signal, outcome)
        values = [_outcome_values(outcome) for outcome in outcome_rows]
        with closing(self._connect()) as connection:
            cursor = connection.cursor()
            for row in values:
                cursor.execute(f"DELETE FROM signal_outcomes WHERE signal_id = {placeholder} AND horizon_trading_days = {placeholder} AND outcome_family = {placeholder}", (row[0], row[1], row[-2]))
                cursor.execute(f"INSERT INTO signal_outcomes ({', '.join(OUTCOME_COLUMNS)}) VALUES ({', '.join([placeholder] * len(row))})", row)
            connection.commit()

    def list_outcomes(self, *, signal_ids: Iterable[str] | None = None, outcome_family: OutcomeFamily | str | None = None) -> tuple[SignalOutcome, ...]:
        self.initialize(); placeholder = "%s" if self.target.backend == REPOSITORY_BACKEND_POSTGRES else "?"
        ids = tuple(signal_ids or ()); clauses, params = [], []
        if ids:
            clauses.append(f"signal_id IN ({', '.join([placeholder] * len(ids))})")
            params.extend(ids)
        if outcome_family is not None:
            clauses.append(f"outcome_family = {placeholder}")
            params.append(OutcomeFamily(outcome_family).value)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        with closing(self._connect()) as connection:
            cursor = connection.cursor(); cursor.execute(f"SELECT {', '.join(OUTCOME_COLUMNS)} FROM signal_outcomes{where} ORDER BY horizon_trading_days, signal_id", tuple(params))
            return tuple(_outcome_from_row(row) for row in cursor.fetchall())


def signal_repository_from_env(env: dict[str, str] | None = None) -> SignalRepository:
    return SignalRepository(research_repository_target_from_env(env))


def _signal_values(signal: Signal) -> tuple:
    return (signal.signal_id, signal.ticker, signal.as_of, signal.model_id, signal.model_version, signal.direction.value, signal.conviction, signal.confidence, signal.reasoning, json.dumps(signal.components, sort_keys=True, separators=(",", ":")), json.dumps(signal.metadata, sort_keys=True, separators=(",", ":")), json.dumps(signal.evidence_refs), signal.created_at, signal.signal_family.value)


def _signal_from_row(row) -> Signal:
    values = dict(zip(SIGNAL_COLUMNS, row, strict=True))
    values["direction"] = SignalDirection(values["direction"]); values["signal_family"] = SignalFamily(values["signal_family"]); values["components"] = json.loads(values["components"]); values["metadata"] = json.loads(values["metadata"]); values["evidence_refs"] = tuple(json.loads(values["evidence_refs"]))
    return Signal(**values)


def _outcome_values(outcome: SignalOutcome) -> tuple:
    return (outcome.signal_id, outcome.horizon_trading_days, outcome.start_date, outcome.end_date, outcome.start_price, outcome.end_price, outcome.absolute_return, outcome.directional_correct, outcome.status.value, outcome.error, outcome.evaluated_at, outcome.outcome_family.value, json.dumps(outcome.components, sort_keys=True, separators=(",", ":")))


def _outcome_from_row(row) -> SignalOutcome:
    values = dict(zip(OUTCOME_COLUMNS, row, strict=True)); values["status"] = OutcomeStatus(values["status"]); values["outcome_family"] = OutcomeFamily(values["outcome_family"]); values["components"] = json.loads(values["components"])
    if values["directional_correct"] is not None: values["directional_correct"] = bool(values["directional_correct"])
    return SignalOutcome(**values)


def _ensure_sqlite_family_columns(connection: sqlite3.Connection) -> None:
    """Add deterministic v0.2 defaults to databases created by v0.1."""
    signal_columns = {row[1] for row in connection.execute("PRAGMA table_info(research_signals)")}
    if "signal_family" not in signal_columns:
        connection.execute(
            "ALTER TABLE research_signals ADD COLUMN signal_family TEXT NOT NULL DEFAULT 'directional'"
        )
    outcome_columns = {row[1] for row in connection.execute("PRAGMA table_info(signal_outcomes)")}
    if "outcome_family" not in outcome_columns:
        connection.execute(
            "ALTER TABLE signal_outcomes ADD COLUMN outcome_family TEXT NOT NULL DEFAULT 'return'"
        )
    if "components" not in outcome_columns:
        connection.execute(
            "ALTER TABLE signal_outcomes ADD COLUMN components TEXT NOT NULL DEFAULT '{}'"
        )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_research_signals_family_asof ON research_signals(signal_family, as_of)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_signal_outcomes_family_horizon ON signal_outcomes(outcome_family, horizon_trading_days)"
    )
