"""Durable immutable storage for versioned Universe Analysis snapshots.

History is ordered by observation_as_of DESC, completed_at DESC, snapshot_id DESC.
No legacy technical scan is promoted into this table; only complete snapshot payloads
written through this repository are returned.
"""
from __future__ import annotations

import json
import sqlite3
from abc import ABC, abstractmethod
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.research_repository import (
    DEFAULT_RESEARCH_DB_PATH,
    REPOSITORY_BACKEND_POSTGRES,
    REPOSITORY_BACKEND_SQLITE,
    ResearchRepositoryTarget,
    research_repository_target_from_env,
)
from src.universe_analysis_contracts import (
    SNAPSHOT_SCHEMA_VERSION,
    SnapshotStatus,
    UniverseAnalysisSnapshotV1,
    validate_universe_analysis_snapshot_v1,
)


SNAPSHOT_TABLE = "universe_analysis_snapshots"
SNAPSHOT_COLUMNS = (
    "snapshot_id", "schema_version", "universe_id", "universe_version",
    "membership_digest", "analysis_run_id", "status", "observation_as_of",
    "completed_at", "persisted_at", "analysis_version", "scoring_version",
    "presentation_version", "snapshot_json",
)
SNAPSHOT_ORDER_SQL = (
    "observation_as_of DESC, completed_at DESC, snapshot_id DESC"
)

SQLITE_SCHEMA = f"""
CREATE TABLE IF NOT EXISTS {SNAPSHOT_TABLE} (
    snapshot_id TEXT PRIMARY KEY,
    schema_version TEXT NOT NULL,
    universe_id TEXT NOT NULL,
    universe_version INTEGER NOT NULL,
    membership_digest TEXT NOT NULL,
    analysis_run_id TEXT NOT NULL,
    status TEXT NOT NULL,
    observation_as_of TEXT NOT NULL,
    completed_at TEXT NOT NULL,
    persisted_at TEXT NOT NULL,
    analysis_version TEXT NOT NULL,
    scoring_version TEXT NOT NULL,
    presentation_version TEXT NOT NULL,
    snapshot_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_universe_analysis_snapshot_history
    ON {SNAPSHOT_TABLE} (universe_id, universe_version, observation_as_of DESC, completed_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS idx_universe_analysis_snapshot_run
    ON {SNAPSHOT_TABLE} (analysis_run_id);
"""

POSTGRES_SCHEMA_STATEMENTS = (
    f"""
    CREATE TABLE IF NOT EXISTS {SNAPSHOT_TABLE} (
        snapshot_id TEXT PRIMARY KEY,
        schema_version TEXT NOT NULL,
        universe_id TEXT NOT NULL,
        universe_version INTEGER NOT NULL,
        membership_digest TEXT NOT NULL,
        analysis_run_id TEXT NOT NULL,
        status TEXT NOT NULL,
        observation_as_of TEXT NOT NULL,
        completed_at TEXT NOT NULL,
        persisted_at TEXT NOT NULL,
        analysis_version TEXT NOT NULL,
        scoring_version TEXT NOT NULL,
        presentation_version TEXT NOT NULL,
        snapshot_json TEXT NOT NULL
    )
    """,
    f"""CREATE INDEX IF NOT EXISTS idx_universe_analysis_snapshot_history
        ON {SNAPSHOT_TABLE} (universe_id, universe_version, observation_as_of DESC, completed_at DESC)""",
    f"""CREATE UNIQUE INDEX IF NOT EXISTS idx_universe_analysis_snapshot_run
        ON {SNAPSHOT_TABLE} (analysis_run_id)""",
)


class SnapshotPersistenceError(RuntimeError):
    pass


class SnapshotConflictError(SnapshotPersistenceError):
    pass


class SnapshotSchemaError(SnapshotPersistenceError):
    pass


@dataclass(frozen=True, slots=True)
class SnapshotHistorySummary:
    universe_id: str
    universe_version: int | None
    snapshot_count: int
    latest_snapshot_id: str | None
    latest_observation_as_of: str | None
    latest_membership_digest: str | None


class UniverseAnalysisSnapshotRepository(ABC):
    @abstractmethod
    def initialize(self) -> None: ...

    @abstractmethod
    def save(self, snapshot: UniverseAnalysisSnapshotV1) -> UniverseAnalysisSnapshotV1: ...

    @abstractmethod
    def get(self, snapshot_id: str) -> UniverseAnalysisSnapshotV1 | None: ...

    @abstractmethod
    def list_for_universe(self, universe_id: str, universe_version: int | None = None) -> tuple[UniverseAnalysisSnapshotV1, ...]: ...

    def get_latest_for_universe(
        self, universe_id: str, universe_version: int | None = None,
        *, completed_only: bool = True,
    ) -> UniverseAnalysisSnapshotV1 | None:
        snapshots = self.list_for_universe(universe_id, universe_version)
        return next((item for item in snapshots if not completed_only or item.status == SnapshotStatus.COMPLETED), None)

    def get_previous_candidate(
        self, universe_id: str, universe_version: int, *, before_snapshot_id: str,
    ) -> UniverseAnalysisSnapshotV1 | None:
        """Return the next older record only; future code decides comparability."""
        snapshots = self.list_for_universe(universe_id, universe_version)
        for index, snapshot in enumerate(snapshots):
            if snapshot.snapshot_id == before_snapshot_id:
                return snapshots[index + 1] if index + 1 < len(snapshots) else None
        return None

    def history_summary(self, universe_id: str, universe_version: int | None = None) -> SnapshotHistorySummary:
        snapshots = self.list_for_universe(universe_id, universe_version)
        latest = snapshots[0] if snapshots else None
        return SnapshotHistorySummary(
            universe_id=universe_id, universe_version=universe_version,
            snapshot_count=len(snapshots),
            latest_snapshot_id=latest.snapshot_id if latest else None,
            latest_observation_as_of=latest.observation_as_of if latest else None,
            latest_membership_digest=latest.membership_digest if latest else None,
        )


class SQLiteUniverseAnalysisSnapshotRepository(UniverseAnalysisSnapshotRepository):
    def __init__(self, database_path: Path | str = DEFAULT_RESEARCH_DB_PATH):
        self.database_path = Path(database_path)

    def initialize(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.executescript(SQLITE_SCHEMA)
            connection.commit()

    def save(self, snapshot: UniverseAnalysisSnapshotV1) -> UniverseAnalysisSnapshotV1:
        values, payload = _snapshot_values(snapshot)
        self.initialize()
        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.execute("BEGIN")
            existing = connection.execute(
                f"SELECT snapshot_json FROM {SNAPSHOT_TABLE} WHERE snapshot_id = ?",
                (snapshot.snapshot_id,),
            ).fetchone()
            if existing:
                if existing[0] == payload:
                    connection.rollback()
                    return snapshot
                connection.rollback()
                raise SnapshotConflictError(
                    f"Snapshot {snapshot.snapshot_id} already exists with different content."
                )
            try:
                connection.execute(
                    f"INSERT INTO {SNAPSHOT_TABLE} ({', '.join(SNAPSHOT_COLUMNS)}) "
                    f"VALUES ({', '.join(['?'] * len(SNAPSHOT_COLUMNS))})",
                    values,
                )
                connection.commit()
            except sqlite3.IntegrityError as error:
                connection.rollback()
                raise SnapshotConflictError(f"Snapshot identity conflict: {error}") from error
        return snapshot

    def get(self, snapshot_id: str) -> UniverseAnalysisSnapshotV1 | None:
        self.initialize()
        with closing(sqlite3.connect(self.database_path)) as connection:
            row = connection.execute(
                f"SELECT snapshot_json FROM {SNAPSHOT_TABLE} WHERE snapshot_id = ?",
                (snapshot_id,),
            ).fetchone()
        return _deserialize(row[0]) if row else None

    def list_for_universe(self, universe_id: str, universe_version: int | None = None) -> tuple[UniverseAnalysisSnapshotV1, ...]:
        self.initialize()
        statement = f"SELECT snapshot_json FROM {SNAPSHOT_TABLE} WHERE universe_id = ?"
        params: list[Any] = [universe_id]
        if universe_version is not None:
            statement += " AND universe_version = ?"
            params.append(universe_version)
        statement += f" ORDER BY {SNAPSHOT_ORDER_SQL}"
        with closing(sqlite3.connect(self.database_path)) as connection:
            rows = connection.execute(statement, tuple(params)).fetchall()
        return tuple(_deserialize(row[0]) for row in rows)


class PostgresUniverseAnalysisSnapshotRepository(UniverseAnalysisSnapshotRepository):
    def __init__(self, database_url: str):
        if not database_url:
            raise ValueError("DATABASE_URL is required for Postgres snapshot persistence.")
        self.database_url = database_url

    def _connect(self):
        try:
            import psycopg
        except ImportError as error:
            raise RuntimeError("Postgres snapshot persistence requires psycopg.") from error
        return psycopg.connect(self.database_url)

    def initialize(self) -> None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                for statement in POSTGRES_SCHEMA_STATEMENTS:
                    cursor.execute(statement)
            connection.commit()

    def save(self, snapshot: UniverseAnalysisSnapshotV1) -> UniverseAnalysisSnapshotV1:
        values, payload = _snapshot_values(snapshot)
        self.initialize()
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"SELECT snapshot_json FROM {SNAPSHOT_TABLE} WHERE snapshot_id = %s",
                    (snapshot.snapshot_id,),
                )
                existing = cursor.fetchone()
                if existing:
                    if existing[0] == payload:
                        return snapshot
                    raise SnapshotConflictError(
                        f"Snapshot {snapshot.snapshot_id} already exists with different content."
                    )
                cursor.execute(
                    f"INSERT INTO {SNAPSHOT_TABLE} ({', '.join(SNAPSHOT_COLUMNS)}) "
                    f"VALUES ({', '.join(['%s'] * len(SNAPSHOT_COLUMNS))})",
                    values,
                )
            connection.commit()
        return snapshot

    def get(self, snapshot_id: str) -> UniverseAnalysisSnapshotV1 | None:
        self.initialize()
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"SELECT snapshot_json FROM {SNAPSHOT_TABLE} WHERE snapshot_id = %s",
                    (snapshot_id,),
                )
                row = cursor.fetchone()
        return _deserialize(row[0]) if row else None

    def list_for_universe(self, universe_id: str, universe_version: int | None = None) -> tuple[UniverseAnalysisSnapshotV1, ...]:
        self.initialize()
        statement = f"SELECT snapshot_json FROM {SNAPSHOT_TABLE} WHERE universe_id = %s"
        params: list[Any] = [universe_id]
        if universe_version is not None:
            statement += " AND universe_version = %s"
            params.append(universe_version)
        statement += f" ORDER BY {SNAPSHOT_ORDER_SQL}"
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(statement, tuple(params))
                rows = cursor.fetchall()
        return tuple(_deserialize(row[0]) for row in rows)


def universe_analysis_snapshot_repository_from_target(
    target: ResearchRepositoryTarget,
) -> UniverseAnalysisSnapshotRepository:
    if target.backend == REPOSITORY_BACKEND_SQLITE:
        return SQLiteUniverseAnalysisSnapshotRepository(target.sqlite_path or DEFAULT_RESEARCH_DB_PATH)
    if target.backend == REPOSITORY_BACKEND_POSTGRES:
        return PostgresUniverseAnalysisSnapshotRepository(target.database_url or "")
    raise ValueError(f"Unsupported snapshot repository backend: {target.backend}")


def universe_analysis_snapshot_repository_from_env(
    env: dict[str, str] | None = None,
) -> UniverseAnalysisSnapshotRepository:
    return universe_analysis_snapshot_repository_from_target(
        research_repository_target_from_env(env)
    )


def _canonical_payload(snapshot: UniverseAnalysisSnapshotV1) -> str:
    validate_universe_analysis_snapshot_v1(snapshot)
    try:
        return json.dumps(
            snapshot.to_dict(), sort_keys=True, separators=(",", ":"),
            ensure_ascii=False, allow_nan=False,
        )
    except (TypeError, ValueError) as error:
        raise SnapshotPersistenceError(f"Snapshot serialization failed: {error}") from error


def _snapshot_values(snapshot: UniverseAnalysisSnapshotV1) -> tuple[tuple[Any, ...], str]:
    if snapshot.schema_version != SNAPSHOT_SCHEMA_VERSION:
        raise SnapshotSchemaError(f"Unsupported snapshot schema: {snapshot.schema_version!r}.")
    payload = _canonical_payload(snapshot)
    persisted_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    manifest = snapshot.version_manifest
    return (
        snapshot.snapshot_id, snapshot.schema_version, snapshot.universe_id,
        snapshot.universe_version, snapshot.membership_digest, snapshot.analysis_run_id,
        snapshot.status.value, snapshot.observation_as_of or snapshot.completed_at,
        snapshot.completed_at, persisted_at, manifest.technical_analysis_version,
        manifest.technical_scoring_version, manifest.presentation_version, payload,
    ), payload


def _deserialize(payload: str) -> UniverseAnalysisSnapshotV1:
    try:
        value = json.loads(payload)
    except (TypeError, json.JSONDecodeError) as error:
        raise SnapshotPersistenceError(f"Stored snapshot JSON is invalid: {error}") from error
    try:
        return UniverseAnalysisSnapshotV1.from_dict(value)
    except ValueError as error:
        raise SnapshotSchemaError(str(error)) from error
