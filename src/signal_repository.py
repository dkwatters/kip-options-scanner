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
from src.signal_outcomes import OutcomeStatus, SignalOutcome
from src.signals import Signal, SignalDirection

SIGNAL_COLUMNS = ("signal_id", "ticker", "as_of", "model_id", "model_version", "direction", "conviction", "confidence", "reasoning", "components", "metadata", "evidence_refs", "created_at")
OUTCOME_COLUMNS = ("signal_id", "horizon_trading_days", "start_date", "end_date", "start_price", "end_price", "absolute_return", "directional_correct", "status", "error", "evaluated_at")

SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS research_signals (
 signal_id TEXT PRIMARY KEY, ticker TEXT NOT NULL, as_of TEXT NOT NULL,
 model_id TEXT NOT NULL, model_version TEXT NOT NULL, direction TEXT NOT NULL,
 conviction REAL NOT NULL, confidence REAL, reasoning TEXT NOT NULL,
 components TEXT NOT NULL, metadata TEXT NOT NULL, evidence_refs TEXT NOT NULL,
 created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_research_signals_security_asof ON research_signals(ticker, as_of);
CREATE INDEX IF NOT EXISTS idx_research_signals_model_asof ON research_signals(model_id, model_version, as_of);
CREATE TABLE IF NOT EXISTS signal_outcomes (
 signal_id TEXT NOT NULL, horizon_trading_days INTEGER NOT NULL,
 start_date TEXT, end_date TEXT, start_price REAL, end_price REAL,
 absolute_return REAL, directional_correct INTEGER, status TEXT NOT NULL,
 error TEXT, evaluated_at TEXT NOT NULL,
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
     components TEXT NOT NULL, metadata TEXT NOT NULL, evidence_refs TEXT NOT NULL, created_at TEXT NOT NULL)""",
    "CREATE INDEX IF NOT EXISTS idx_research_signals_security_asof ON research_signals(ticker, as_of)",
    "CREATE INDEX IF NOT EXISTS idx_research_signals_model_asof ON research_signals(model_id, model_version, as_of)",
    """CREATE TABLE IF NOT EXISTS signal_outcomes (
     signal_id TEXT NOT NULL REFERENCES research_signals(signal_id), horizon_trading_days INTEGER NOT NULL,
     start_date TEXT, end_date TEXT, start_price DOUBLE PRECISION, end_price DOUBLE PRECISION,
     absolute_return DOUBLE PRECISION, directional_correct BOOLEAN, status TEXT NOT NULL,
     error TEXT, evaluated_at TEXT NOT NULL, PRIMARY KEY(signal_id, horizon_trading_days))""",
    "CREATE INDEX IF NOT EXISTS idx_signal_outcomes_status_horizon ON signal_outcomes(status, horizon_trading_days)",
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

    def list_signals(self, *, ticker: str | None = None, model_id: str | None = None, model_version: str | None = None, as_of_start: str | None = None, as_of_end: str | None = None) -> tuple[Signal, ...]:
        self.initialize()
        placeholder = "%s" if self.target.backend == REPOSITORY_BACKEND_POSTGRES else "?"
        clauses, params = [], []
        for column, value, operator in (("ticker", ticker.upper() if ticker else None, "="), ("model_id", model_id, "="), ("model_version", model_version, "="), ("as_of", as_of_start, ">="), ("as_of", as_of_end, "<=")):
            if value is not None:
                clauses.append(f"{column} {operator} {placeholder}"); params.append(value)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        with closing(self._connect()) as connection:
            cursor = connection.cursor(); cursor.execute(f"SELECT {', '.join(SIGNAL_COLUMNS)} FROM research_signals{where} ORDER BY as_of DESC, signal_id", tuple(params))
            return tuple(_signal_from_row(row) for row in cursor.fetchall())

    def save_outcomes(self, outcomes: Iterable[SignalOutcome]) -> None:
        self.initialize(); placeholder = "%s" if self.target.backend == REPOSITORY_BACKEND_POSTGRES else "?"
        values = [_outcome_values(outcome) for outcome in outcomes]
        with closing(self._connect()) as connection:
            cursor = connection.cursor()
            for row in values:
                cursor.execute(f"DELETE FROM signal_outcomes WHERE signal_id = {placeholder} AND horizon_trading_days = {placeholder}", row[:2])
                cursor.execute(f"INSERT INTO signal_outcomes ({', '.join(OUTCOME_COLUMNS)}) VALUES ({', '.join([placeholder] * len(row))})", row)
            connection.commit()

    def list_outcomes(self, *, signal_ids: Iterable[str] | None = None) -> tuple[SignalOutcome, ...]:
        self.initialize(); placeholder = "%s" if self.target.backend == REPOSITORY_BACKEND_POSTGRES else "?"
        ids = tuple(signal_ids or ()); where, params = "", ()
        if ids: where, params = f" WHERE signal_id IN ({', '.join([placeholder] * len(ids))})", ids
        with closing(self._connect()) as connection:
            cursor = connection.cursor(); cursor.execute(f"SELECT {', '.join(OUTCOME_COLUMNS)} FROM signal_outcomes{where} ORDER BY horizon_trading_days, signal_id", params)
            return tuple(_outcome_from_row(row) for row in cursor.fetchall())


def signal_repository_from_env(env: dict[str, str] | None = None) -> SignalRepository:
    return SignalRepository(research_repository_target_from_env(env))


def _signal_values(signal: Signal) -> tuple:
    return (signal.signal_id, signal.ticker, signal.as_of, signal.model_id, signal.model_version, signal.direction.value, signal.conviction, signal.confidence, signal.reasoning, json.dumps(signal.components, sort_keys=True, separators=(",", ":")), json.dumps(signal.metadata, sort_keys=True, separators=(",", ":")), json.dumps(signal.evidence_refs), signal.created_at)


def _signal_from_row(row) -> Signal:
    values = dict(zip(SIGNAL_COLUMNS, row, strict=True))
    values["direction"] = SignalDirection(values["direction"]); values["components"] = json.loads(values["components"]); values["metadata"] = json.loads(values["metadata"]); values["evidence_refs"] = tuple(json.loads(values["evidence_refs"]))
    return Signal(**values)


def _outcome_values(outcome: SignalOutcome) -> tuple:
    return (outcome.signal_id, outcome.horizon_trading_days, outcome.start_date, outcome.end_date, outcome.start_price, outcome.end_price, outcome.absolute_return, outcome.directional_correct, outcome.status.value, outcome.error, outcome.evaluated_at)


def _outcome_from_row(row) -> SignalOutcome:
    values = dict(zip(OUTCOME_COLUMNS, row, strict=True)); values["status"] = OutcomeStatus(values["status"])
    if values["directional_correct"] is not None: values["directional_correct"] = bool(values["directional_correct"])
    return SignalOutcome(**values)
