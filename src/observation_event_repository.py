"""Persistence for immutable Signal-to-Signal Observation Events."""
from __future__ import annotations

from contextlib import closing
import json
from pathlib import Path
import sqlite3
from typing import Iterable

from src.observation_events import ObservationEvent, ObservationEventImportance, event_json_value, signal_instant
from src.research_repository import DEFAULT_RESEARCH_DB_PATH, REPOSITORY_BACKEND_POSTGRES, ResearchRepositoryTarget
from src.signals import SignalFamily
from src.observation_comparisons import (COMPARISON_DDL, COMPARISON_COLUMNS,
    COMPARISON_POLICY_VERSION, comparison_values, comparison_from_row)


EVENT_COLUMNS = (
    "event_id", "ticker", "observed_at", "signal_family", "model_id", "model_version",
    "event_type", "prior_signal_id", "current_signal_id", "prior_as_of", "current_as_of",
    "field", "prior_value", "current_value", "importance", "components", "metadata",
    "source_scan_id", "created_at", "schema_version",
)
SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS observation_events (
 event_id TEXT PRIMARY KEY, ticker TEXT NOT NULL, observed_at TEXT NOT NULL,
 signal_family TEXT NOT NULL, model_id TEXT NOT NULL, model_version TEXT NOT NULL,
 event_type TEXT NOT NULL, prior_signal_id TEXT NOT NULL, current_signal_id TEXT NOT NULL,
 prior_as_of TEXT NOT NULL, current_as_of TEXT NOT NULL, field TEXT NOT NULL,
 prior_value TEXT NOT NULL, current_value TEXT NOT NULL, importance TEXT NOT NULL,
 components TEXT NOT NULL, metadata TEXT NOT NULL, source_scan_id TEXT, created_at TEXT NOT NULL,
 schema_version TEXT NOT NULL,
 FOREIGN KEY(prior_signal_id) REFERENCES research_signals(signal_id),
 FOREIGN KEY(current_signal_id) REFERENCES research_signals(signal_id)
);
CREATE INDEX IF NOT EXISTS idx_observation_events_ticker_observed ON observation_events(ticker, observed_at);
CREATE INDEX IF NOT EXISTS idx_observation_events_model_observed ON observation_events(signal_family, model_id, model_version, observed_at);
"""
POSTGRES_SCHEMA = tuple(statement.strip() for statement in (
    """CREATE TABLE IF NOT EXISTS observation_events (
     event_id TEXT PRIMARY KEY, ticker TEXT NOT NULL, observed_at TEXT NOT NULL,
     signal_family TEXT NOT NULL, model_id TEXT NOT NULL, model_version TEXT NOT NULL,
     event_type TEXT NOT NULL, prior_signal_id TEXT NOT NULL REFERENCES research_signals(signal_id),
     current_signal_id TEXT NOT NULL REFERENCES research_signals(signal_id),
     prior_as_of TEXT NOT NULL, current_as_of TEXT NOT NULL, field TEXT NOT NULL,
     prior_value TEXT NOT NULL, current_value TEXT NOT NULL, importance TEXT NOT NULL,
     components TEXT NOT NULL, metadata TEXT NOT NULL, source_scan_id TEXT,
     created_at TEXT NOT NULL, schema_version TEXT NOT NULL)""",
    "CREATE INDEX IF NOT EXISTS idx_observation_events_ticker_observed ON observation_events(ticker, observed_at)",
    "CREATE INDEX IF NOT EXISTS idx_observation_events_model_observed ON observation_events(signal_family, model_id, model_version, observed_at)",
) if statement)


class ObservationEventConflict(ValueError):
    """Raised when immutable content conflicts with an existing event identity."""


class ObservationComparisonConflict(ValueError):
    """Immutable comparison content or event lineage conflicts."""


class ObservationEventRepository:
    def __init__(self, target: ResearchRepositoryTarget): self.target = target

    def _connect(self):
        if self.target.backend == REPOSITORY_BACKEND_POSTGRES:
            import psycopg
            return psycopg.connect(self.target.database_url)
        path = Path(self.target.sqlite_path or DEFAULT_RESEARCH_DB_PATH)
        path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(path); connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def initialize(self) -> None:
        with closing(self._connect()) as connection:
            if self.target.backend == REPOSITORY_BACKEND_POSTGRES:
                with connection.cursor() as cursor:
                    for statement in (*POSTGRES_SCHEMA, *COMPARISON_DDL): cursor.execute(statement)
            else: connection.executescript(SQLITE_SCHEMA + ";".join(COMPARISON_DDL) + ";")
            connection.commit()

    def save_events(self, events: Iterable[ObservationEvent]) -> tuple[bool, ...]:
        self.initialize(); placeholder = "%s" if self.target.backend == REPOSITORY_BACKEND_POSTGRES else "?"
        with closing(self._connect()) as connection:
            cursor = connection.cursor(); inserted = []
            try:
                inserted = self._save_events(cursor, events, placeholder)
                connection.commit()
            except Exception:
                connection.rollback(); raise
        return tuple(inserted)

    def _save_events(self, cursor, events, placeholder):
        inserted = []
        for event in events:
            values = _values(event)
            cursor.execute(
                f"INSERT INTO observation_events ({', '.join(EVENT_COLUMNS)}) VALUES ({', '.join([placeholder] * len(values))}) ON CONFLICT(event_id) DO NOTHING",
                values,
            )
            inserted.append(cursor.rowcount == 1)
            cursor.execute(f"SELECT {', '.join(EVENT_COLUMNS)} FROM observation_events WHERE event_id = {placeholder}", (event.event_id,))
            if tuple(cursor.fetchone()) != values:
                raise ObservationEventConflict(f"Observation Event {event.event_id} already exists with different immutable content.")
        return inserted

    def get_comparison(self, current_signal_id, policy_version=COMPARISON_POLICY_VERSION):
        self.initialize()
        placeholder = "%s" if self.target.backend == REPOSITORY_BACKEND_POSTGRES else "?"
        with closing(self._connect()) as connection:
            cursor = connection.cursor()
            cursor.execute(f"SELECT {', '.join(COMPARISON_COLUMNS)} FROM observation_comparisons WHERE current_signal_id = {placeholder} AND policy_version = {placeholder}", (current_signal_id, policy_version))
            row = cursor.fetchone()
            if row is None:
                return None
            comparison = comparison_from_row(row)
            cursor.execute(f"SELECT comparison_id FROM observation_comparison_completions WHERE comparison_id = {placeholder}", (comparison.comparison_id,))
            return comparison, cursor.fetchone() is not None

    def save_comparison(self, comparison, *, accept_existing=False):
        """Reserve immutable selection durably; production races return the winning selection."""
        self.initialize()
        placeholder = "%s" if self.target.backend == REPOSITORY_BACKEND_POSTGRES else "?"
        values = comparison_values(comparison)
        with closing(self._connect()) as connection:
            cursor = connection.cursor()
            try:
                cursor.execute(f"INSERT INTO observation_comparisons ({', '.join(COMPARISON_COLUMNS)}) VALUES ({', '.join([placeholder] * len(values))}) ON CONFLICT(current_signal_id, policy_version) DO NOTHING", values)
                inserted = cursor.rowcount == 1
                cursor.execute(f"SELECT {', '.join(COMPARISON_COLUMNS)} FROM observation_comparisons WHERE current_signal_id = {placeholder} AND policy_version = {placeholder}", (comparison.current_signal_id, comparison.policy_version))
                row = cursor.fetchone()
                if not accept_existing and tuple(row) != values:
                    raise ObservationComparisonConflict("Comparison already exists with different immutable content")
                connection.commit()
                return comparison_from_row(row), inserted
            except Exception:
                connection.rollback()
                raise

    def complete_comparison(self, comparison, events):
        """Commit all events and the completion receipt together, including zero-event results."""
        events = tuple(events)
        if len(events) != comparison.event_count or len({e.event_id for e in events}) != len(events):
            raise ObservationComparisonConflict("Comparison event count does not match evidence")
        if tuple(e.event_id for e in events) != tuple(comparison.metadata.get("event_ids", ())):
            raise ObservationComparisonConflict("Comparison event identities do not match evidence")
        for event in events:
            if (event.current_signal_id, event.prior_signal_id, event.ticker, event.signal_family,
                event.model_id, event.model_version, event.current_as_of, event.prior_as_of) != (
                comparison.current_signal_id, comparison.prior_signal_id, comparison.ticker,
                comparison.signal_family, comparison.model_id, comparison.model_version,
                comparison.current_as_of, comparison.prior_as_of):
                raise ObservationComparisonConflict("Event lineage does not match comparison")
        placeholder = "%s" if self.target.backend == REPOSITORY_BACKEND_POSTGRES else "?"
        with closing(self._connect()) as connection:
            cursor = connection.cursor()
            try:
                # Serialize completion for the same selection on both supported backends.
                if self.target.backend == REPOSITORY_BACKEND_POSTGRES:
                    lock = " FOR UPDATE"
                else:
                    connection.execute("BEGIN IMMEDIATE")
                    lock = ""
                cursor.execute(f"SELECT {', '.join(COMPARISON_COLUMNS)} FROM observation_comparisons WHERE comparison_id = {placeholder}{lock}", (comparison.comparison_id,))
                row = cursor.fetchone()
                if row is None or tuple(row) != comparison_values(comparison):
                    raise ObservationComparisonConflict("Comparison reservation is missing or conflicts")
                cursor.execute(f"SELECT comparison_id FROM observation_comparison_completions WHERE comparison_id = {placeholder}", (comparison.comparison_id,))
                completed = cursor.fetchone() is not None
                inserted = self._save_events(cursor, events, placeholder)
                cursor.execute(f"INSERT INTO observation_comparison_completions (comparison_id) VALUES ({placeholder}) ON CONFLICT(comparison_id) DO NOTHING", (comparison.comparison_id,))
                connection.commit()
                return tuple(inserted), completed
            except Exception:
                connection.rollback()
                raise

    def list_events(self, *, ticker: str | None = None, signal_family: SignalFamily | str | None = None,
                    model_id: str | None = None, model_version: str | None = None,
                    limit: int | None = None, current_signal_id: str | None = None) -> tuple[ObservationEvent, ...]:
        self.initialize(); placeholder = "%s" if self.target.backend == REPOSITORY_BACKEND_POSTGRES else "?"
        clauses, params = [], []
        family = SignalFamily(signal_family).value if signal_family is not None else None
        for column, value in (("ticker", ticker.upper() if ticker else None), ("signal_family", family),
                              ("model_id", model_id), ("model_version", model_version), ("current_signal_id", current_signal_id)):
            if value is not None: clauses.append(f"{column} = {placeholder}"); params.append(value)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        with closing(self._connect()) as connection:
            cursor = connection.cursor(); cursor.execute(f"SELECT {', '.join(EVENT_COLUMNS)} FROM observation_events{where}", tuple(params))
            events = sorted((_from_row(row) for row in cursor.fetchall()), key=lambda event: event.event_id)
        # Normalize before limiting: legacy AM/PM and mixed ISO offsets are not lexical time.
        events.sort(key=lambda event: signal_instant(event.observed_at), reverse=True)
        return tuple(events if limit is None else events[:max(0, int(limit))])


def _values(event: ObservationEvent) -> tuple:
    dump = lambda value: json.dumps(event_json_value(value), sort_keys=True, separators=(",", ":"))
    return (event.event_id, event.ticker, event.observed_at, event.signal_family.value,
            event.model_id, event.model_version, event.event_type, event.prior_signal_id,
            event.current_signal_id, event.prior_as_of, event.current_as_of, event.field,
            dump(event.prior_value), dump(event.current_value), event.importance.value,
            dump(event.components), dump(event.metadata), event.source_scan_id, event.created_at,
            event.schema_version)


def _from_row(row) -> ObservationEvent:
    values = dict(zip(EVENT_COLUMNS, row, strict=True))
    for name in ("prior_value", "current_value", "components", "metadata"): values[name] = json.loads(values[name])
    values["signal_family"] = SignalFamily(values["signal_family"])
    values["importance"] = ObservationEventImportance(values["importance"])
    return ObservationEvent(**values)
