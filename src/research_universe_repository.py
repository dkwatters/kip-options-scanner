"""Durable storage and rediscovery for living Research Universe projects."""
from __future__ import annotations

import json
import sqlite3
from abc import ABC, abstractmethod
from contextlib import closing
from dataclasses import dataclass, replace
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
from src.research_universe import (
    CandidateDisposition,
    IdentityStatus,
    ResearchUniverse,
    ResearchUniverseReviewService,
    UniverseCandidate,
    UniverseSource,
    UniverseSourceRecord,
    UniverseState,
    UniverseType,
    source_record,
    validate_candidate_partition_integrity,
)
from src.universe_analysis_contracts import UniverseAnalysisSnapshotV1


UNIVERSE_TABLE = "research_universes"
SQLITE_SCHEMA = f"""
CREATE TABLE IF NOT EXISTS {UNIVERSE_TABLE} (
    universe_id TEXT PRIMARY KEY,
    universe_version INTEGER NOT NULL,
    title TEXT NOT NULL,
    state TEXT NOT NULL,
    member_count INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    universe_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_research_universes_updated
    ON {UNIVERSE_TABLE} (updated_at DESC, universe_id);
"""
POSTGRES_SCHEMA = f"""
CREATE TABLE IF NOT EXISTS {UNIVERSE_TABLE} (
    universe_id TEXT PRIMARY KEY,
    universe_version INTEGER NOT NULL,
    title TEXT NOT NULL,
    state TEXT NOT NULL,
    member_count INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    universe_json TEXT NOT NULL
)
"""


@dataclass(frozen=True, slots=True)
class OrphanedUniverseSnapshot:
    universe_id: str
    universe_version: int
    title: str
    member_count: int
    observation_as_of: str
    snapshot: UniverseAnalysisSnapshotV1


class ResearchUniverseRepository(ABC):
    @abstractmethod
    def initialize(self) -> None: ...

    @abstractmethod
    def save(self, universe: ResearchUniverse) -> ResearchUniverse: ...

    @abstractmethod
    def get(self, universe_id: str) -> ResearchUniverse | None: ...

    @abstractmethod
    def list_all(self) -> tuple[ResearchUniverse, ...]: ...

    @abstractmethod
    def list_orphaned_snapshots(self) -> tuple[OrphanedUniverseSnapshot, ...]: ...


class SQLiteResearchUniverseRepository(ResearchUniverseRepository):
    def __init__(self, database_path: Path | str = DEFAULT_RESEARCH_DB_PATH):
        self.database_path = Path(database_path)

    def initialize(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.executescript(SQLITE_SCHEMA)
            connection.commit()

    def save(self, universe: ResearchUniverse) -> ResearchUniverse:
        validate_candidate_partition_integrity(universe.candidates)
        self.initialize()
        payload = _serialize(universe)
        values = (
            universe.universe_id, universe.version, universe.title, universe.state.value,
            len(universe.approved_membership), _iso(universe.created_at),
            _iso(universe.updated_at), payload,
        )
        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.execute(
                f"""INSERT INTO {UNIVERSE_TABLE}
                    (universe_id, universe_version, title, state, member_count,
                     created_at, updated_at, universe_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(universe_id) DO UPDATE SET
                    universe_version=excluded.universe_version, title=excluded.title,
                    state=excluded.state, member_count=excluded.member_count,
                    updated_at=excluded.updated_at, universe_json=excluded.universe_json""",
                values,
            )
            connection.commit()
        return universe

    def get(self, universe_id: str) -> ResearchUniverse | None:
        self.initialize()
        with closing(sqlite3.connect(self.database_path)) as connection:
            row = connection.execute(
                f"SELECT universe_json FROM {UNIVERSE_TABLE} WHERE universe_id = ?",
                (universe_id,),
            ).fetchone()
        return _deserialize(row[0]) if row else None

    def list_all(self) -> tuple[ResearchUniverse, ...]:
        self.initialize()
        with closing(sqlite3.connect(self.database_path)) as connection:
            rows = connection.execute(
                f"SELECT universe_json FROM {UNIVERSE_TABLE} ORDER BY updated_at DESC, universe_id"
            ).fetchall()
        return tuple(_deserialize(row[0]) for row in rows)

    def list_orphaned_snapshots(self) -> tuple[OrphanedUniverseSnapshot, ...]:
        self.initialize()
        with closing(sqlite3.connect(self.database_path)) as connection:
            if not _sqlite_table_exists(connection, "universe_analysis_snapshots"):
                return ()
            rows = connection.execute(
                f"""SELECT s.snapshot_json
                    FROM universe_analysis_snapshots s
                    LEFT JOIN {UNIVERSE_TABLE} u ON u.universe_id = s.universe_id
                    WHERE u.universe_id IS NULL
                    AND s.snapshot_id = (
                        SELECT s2.snapshot_id FROM universe_analysis_snapshots s2
                        WHERE s2.universe_id = s.universe_id
                        ORDER BY s2.observation_as_of DESC, s2.completed_at DESC,
                                 s2.snapshot_id DESC LIMIT 1
                    )
                    ORDER BY s.observation_as_of DESC, s.universe_id"""
            ).fetchall()
        return tuple(_orphan(json.loads(row[0])) for row in rows)


class PostgresResearchUniverseRepository(ResearchUniverseRepository):
    def __init__(self, database_url: str):
        self.database_url = database_url

    def _connect(self):
        try:
            import psycopg
        except ImportError as error:
            raise RuntimeError("Postgres Research Universe persistence requires psycopg.") from error
        return psycopg.connect(self.database_url)

    def initialize(self) -> None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(POSTGRES_SCHEMA)
                cursor.execute(
                    f"CREATE INDEX IF NOT EXISTS idx_research_universes_updated "
                    f"ON {UNIVERSE_TABLE} (updated_at DESC, universe_id)"
                )
            connection.commit()

    def save(self, universe: ResearchUniverse) -> ResearchUniverse:
        validate_candidate_partition_integrity(universe.candidates)
        self.initialize()
        values = (
            universe.universe_id, universe.version, universe.title, universe.state.value,
            len(universe.approved_membership), _iso(universe.created_at),
            _iso(universe.updated_at), _serialize(universe),
        )
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""INSERT INTO {UNIVERSE_TABLE}
                        (universe_id, universe_version, title, state, member_count,
                         created_at, updated_at, universe_json)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT(universe_id) DO UPDATE SET
                        universe_version=excluded.universe_version, title=excluded.title,
                        state=excluded.state, member_count=excluded.member_count,
                        updated_at=excluded.updated_at, universe_json=excluded.universe_json""",
                    values,
                )
            connection.commit()
        return universe

    def get(self, universe_id: str) -> ResearchUniverse | None:
        self.initialize()
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"SELECT universe_json FROM {UNIVERSE_TABLE} WHERE universe_id = %s",
                    (universe_id,),
                )
                row = cursor.fetchone()
        return _deserialize(row[0]) if row else None

    def list_all(self) -> tuple[ResearchUniverse, ...]:
        self.initialize()
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"SELECT universe_json FROM {UNIVERSE_TABLE} ORDER BY updated_at DESC, universe_id"
                )
                rows = cursor.fetchall()
        return tuple(_deserialize(row[0]) for row in rows)

    def list_orphaned_snapshots(self) -> tuple[OrphanedUniverseSnapshot, ...]:
        self.initialize()
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT to_regclass('universe_analysis_snapshots')")
                if cursor.fetchone()[0] is None:
                    return ()
                cursor.execute(
                    f"""SELECT DISTINCT ON (s.universe_id) s.snapshot_json
                        FROM universe_analysis_snapshots s
                        LEFT JOIN {UNIVERSE_TABLE} u ON u.universe_id = s.universe_id
                        WHERE u.universe_id IS NULL
                        ORDER BY s.universe_id, s.observation_as_of DESC,
                                 s.completed_at DESC, s.snapshot_id DESC"""
                )
                rows = cursor.fetchall()
        return tuple(sorted(
            (_orphan(json.loads(row[0])) for row in rows),
            key=lambda row: (row.observation_as_of, row.universe_id), reverse=True,
        ))


def research_universe_repository_from_target(
    target: ResearchRepositoryTarget,
) -> ResearchUniverseRepository:
    if target.backend == REPOSITORY_BACKEND_SQLITE:
        return SQLiteResearchUniverseRepository(target.sqlite_path or DEFAULT_RESEARCH_DB_PATH)
    if target.backend == REPOSITORY_BACKEND_POSTGRES:
        return PostgresResearchUniverseRepository(target.database_url or "")
    raise ValueError(f"Unsupported Research Universe repository backend: {target.backend}")


def research_universe_repository_from_env(
    env: dict[str, str] | None = None,
) -> ResearchUniverseRepository:
    return research_universe_repository_from_target(research_repository_target_from_env(env))


def recover_universe_from_snapshot(snapshot: UniverseAnalysisSnapshotV1) -> ResearchUniverse:
    """Recover the exact analyzed membership; never infer omitted review candidates."""
    ordered = sorted(snapshot.members, key=lambda row: row.membership_order)
    records = tuple(
        source_record(
            {
                "company_name": member.company_name,
                "ticker_or_identifier": member.ticker_or_identifier,
                "identity_status": getattr(member.identity_status, "value", member.identity_status),
                "original_input": member.ticker_or_identifier or member.company_name,
            },
            UniverseSource.SAVED_UNIVERSE_REVISION,
            source_reference=(member.source_references[0] if member.source_references else
                              f"snapshot:{snapshot.snapshot_id}"),
        )
        for member in ordered
    )
    universe = ResearchUniverseReviewService().assemble(
        universe_id=snapshot.universe_id,
        title=snapshot.universe_title,
        research_question=snapshot.research_question,
        starting_companies=records,
        version=snapshot.universe_version,
        state=UniverseState.ANALYZED,
        provenance={
            "persistence": "recovered_from_snapshot",
            "universe_type": UniverseType.PRIVATE_USER,
            "recovered_from_snapshot_id": snapshot.snapshot_id,
            "recovery_scope": "exact analyzed membership only",
        },
    )
    observed = _parse_datetime(snapshot.completed_at)
    return replace(universe, created_at=observed, updated_at=observed,
                   analysis_references=(snapshot.snapshot_id,))


def _serialize(universe: ResearchUniverse) -> str:
    value = {
        "universe_id": universe.universe_id,
        "title": universe.title,
        "research_question": universe.research_question,
        "state": universe.state.value,
        "version": universe.version,
        "created_at": _iso(universe.created_at),
        "updated_at": _iso(universe.updated_at),
        "owner_reference": universe.owner_reference,
        "visibility": universe.visibility,
        "universe_type": universe.universe_type.value,
        "provenance": dict(universe.provenance),
        "analysis_references": list(universe.analysis_references),
        "established_topic": universe.established_topic,
        "candidates": [{
            "normalized_matching_key": candidate.normalized_matching_key,
            "company_name": candidate.company_name,
            "ticker_or_identifier": candidate.ticker_or_identifier,
            "identity_status": candidate.identity_status.value,
            "original_input": candidate.original_input,
            "in_starting_companies": candidate.in_starting_companies,
            "in_rce_suggestions": candidate.in_rce_suggestions,
            "disposition": candidate.disposition.value,
            "inclusion_origin": candidate.inclusion_origin,
            "rejection_reason": candidate.rejection_reason,
            "comment": candidate.comment,
            "rce_rank": candidate.rce_rank,
            "rce_metadata": dict(candidate.rce_metadata),
            "source_records": [{
                "source": record.source.value,
                "company_name": record.company_name,
                "ticker_or_identifier": record.ticker_or_identifier,
                "source_reference": record.source_reference,
                "identity_status": record.identity_status.value,
                "original_input": record.original_input,
                "metadata": dict(record.metadata),
            } for record in candidate.source_records],
        } for candidate in universe.candidates],
    }
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _deserialize(payload: str) -> ResearchUniverse:
    value = json.loads(payload)
    candidates = tuple(
        UniverseCandidate(
            normalized_matching_key=candidate["normalized_matching_key"],
            company_name=candidate["company_name"],
            ticker_or_identifier=candidate.get("ticker_or_identifier"),
            identity_status=IdentityStatus(candidate["identity_status"]),
            original_input=candidate.get("original_input"),
            in_starting_companies=bool(candidate["in_starting_companies"]),
            in_rce_suggestions=bool(candidate["in_rce_suggestions"]),
            source_records=tuple(
                _source_from_dict(item) for item in candidate["source_records"]
            ),
            disposition=CandidateDisposition(candidate["disposition"]),
            inclusion_origin=candidate.get("inclusion_origin"),
            rejection_reason=candidate.get("rejection_reason"),
            comment=candidate.get("comment"),
            rce_rank=candidate.get("rce_rank"),
            rce_metadata=candidate.get("rce_metadata", {}),
        )
        for candidate in value["candidates"]
    )
    return ResearchUniverse(
        universe_id=value["universe_id"], title=value["title"],
        research_question=value.get("research_question", ""),
        state=UniverseState(value["state"]), version=int(value["version"]),
        candidates=candidates, created_at=_parse_datetime(value["created_at"]),
        updated_at=_parse_datetime(value["updated_at"]),
        owner_reference=value.get("owner_reference"),
        visibility=value.get("visibility"),
        universe_type=UniverseType(value.get("universe_type", UniverseType.PRIVATE_USER)),
        provenance=value.get("provenance", {}),
        analysis_references=tuple(value.get("analysis_references", ())),
        established_topic=value.get("established_topic"),
    )


def _source_from_dict(value: dict[str, Any]) -> UniverseSourceRecord:
    return UniverseSourceRecord(
        source=UniverseSource(value["source"]), company_name=value["company_name"],
        ticker_or_identifier=value.get("ticker_or_identifier"),
        source_reference=value.get("source_reference"),
        identity_status=IdentityStatus(value["identity_status"]),
        original_input=value.get("original_input"), metadata=value.get("metadata", {}),
    )


def _orphan(value: dict[str, Any]) -> OrphanedUniverseSnapshot:
    snapshot = UniverseAnalysisSnapshotV1.from_dict(value)
    return OrphanedUniverseSnapshot(
        universe_id=snapshot.universe_id, universe_version=snapshot.universe_version,
        title=snapshot.universe_title, member_count=snapshot.total_universe_member_count,
        observation_as_of=snapshot.observation_as_of or snapshot.completed_at,
        snapshot=snapshot,
    )


def _sqlite_table_exists(connection: sqlite3.Connection, name: str) -> bool:
    return connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone() is not None


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
