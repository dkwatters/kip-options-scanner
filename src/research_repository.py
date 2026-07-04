"""SQLite archive for completed Opportunity Discovery scans.

The research repository is intentionally append-oriented: it stores enough scan
metadata, evaluated contract rows, rule outcomes, and ticker-level summaries to
rebuild future model-validation and longitudinal-analysis datasets without
changing the current Contract Quality Model.
"""
from __future__ import annotations

import sqlite3
from abc import ABC, abstractmethod
from collections import Counter, defaultdict
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime
from math import isfinite
import os
from pathlib import Path
from statistics import mean
from typing import Any
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from src.contract_quality import ALL_PASSED_YES, QUALITY_CHECKS, near_miss_contracts
from src.quality_diagnostics import discovery_diagnostic_summary
from src.rule_evaluation import FAIL
from src.study_protocol import (
    RUN_MODE_MANUAL_UI,
    RUN_MODE_RESEARCH_SCRIPT,
    RUN_MODE_SCHEDULED,
)


DEFAULT_RESEARCH_DB_PATH = Path("data/research/opportunity_scans.sqlite")
REPOSITORY_BACKEND_SQLITE = "sqlite"
REPOSITORY_BACKEND_POSTGRES = "postgres"
RESEARCH_REPOSITORY_BACKEND_ENV = "RESEARCH_REPOSITORY_BACKEND"
RESEARCH_SQLITE_PATH_ENV = "RESEARCH_SQLITE_PATH"
DATABASE_URL_ENV = "DATABASE_URL"
CANONICAL_RUN_MODES = {
    RUN_MODE_MANUAL_UI,
    RUN_MODE_RESEARCH_SCRIPT,
    RUN_MODE_SCHEDULED,
}
LEGACY_RUN_MODE_MAP = {
    "manual": RUN_MODE_MANUAL_UI,
    "app-triggered": RUN_MODE_MANUAL_UI,
}


@dataclass(frozen=True, slots=True)
class ResearchRepositoryTarget:
    backend: str
    sqlite_path: Path | None = None
    database_url: str | None = None

    @property
    def display_location(self) -> str:
        if self.backend == REPOSITORY_BACKEND_SQLITE:
            return str(self.sqlite_path or DEFAULT_RESEARCH_DB_PATH)
        return self.database_url or ""


@dataclass(frozen=True)
class ResearchRepositoryStatus:
    """Small status payload for the Streamlit sidebar/status area."""

    database_path: str
    total_scans: int
    total_contracts_evaluated: int
    total_rule_evaluations: int
    total_security_characterizations: int
    latest_scan_timestamp: str | None
    latest_study_id: str | None
    latest_scan_id: str | None
    latest_scheduled_time_label: str | None
    latest_run_mode: str | None
    latest_rows_written: dict[str, int]
    today_observations: tuple[dict[str, str | None], ...]
    today_completed_schedule_times: tuple[str, ...]
    recent_observations: tuple[dict[str, str | None], ...]


class ResearchRepository(ABC):
    """Storage boundary for archived research observations."""

    @abstractmethod
    def initialize(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def archive_opportunity_scan(self, **kwargs: Any) -> dict[str, int]:
        raise NotImplementedError

    @abstractmethod
    def status(self, study_id: str | None = None) -> ResearchRepositoryStatus:
        raise NotImplementedError

    @abstractmethod
    def latest_scan_row_counts(self) -> dict[str, int | str] | None:
        raise NotImplementedError


class SQLiteResearchRepository(ResearchRepository):
    def __init__(self, database_path: Path | str = DEFAULT_RESEARCH_DB_PATH):
        self.database_path = Path(database_path)

    def initialize(self) -> str:
        return str(initialize_research_repository(self.database_path))

    def archive_opportunity_scan(self, **kwargs: Any) -> dict[str, int]:
        return archive_opportunity_scan(database_path=self.database_path, **kwargs)

    def status(self, study_id: str | None = None) -> ResearchRepositoryStatus:
        return research_repository_status(self.database_path, study_id=study_id)

    def latest_scan_row_counts(self) -> dict[str, int | str] | None:
        return latest_scan_row_counts(self.database_path)


class PostgresResearchRepository(ResearchRepository):
    def __init__(self, database_url: str):
        if not database_url:
            raise ValueError("DATABASE_URL is required for the postgres research repository.")
        self.database_url = database_url

    def initialize(self) -> str:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                for statement in POSTGRES_SCHEMA_STATEMENTS:
                    cursor.execute(statement)
                cursor.execute(
                    """
                    UPDATE opportunity_scans
                    SET run_mode = %s
                    WHERE run_mode IS NULL
                       OR run_mode = ''
                       OR run_mode IN ('manual', 'app-triggered')
                    """,
                    (RUN_MODE_MANUAL_UI,),
                )
            connection.commit()
        return self.database_url

    def archive_opportunity_scan(self, **kwargs: Any) -> dict[str, int]:
        self.initialize()
        archive_payload = _archive_payload(**kwargs)

        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM evaluated_contracts WHERE scan_id = %s",
                    (archive_payload["scan_id"],),
                )
                cursor.execute(
                    "DELETE FROM rule_evaluations WHERE scan_id = %s",
                    (archive_payload["scan_id"],),
                )
                cursor.execute(
                    "DELETE FROM security_characterization WHERE scan_id = %s",
                    (archive_payload["scan_id"],),
                )
                cursor.execute(
                    POSTGRES_OPPORTUNITY_SCAN_UPSERT,
                    archive_payload["opportunity_scan_values"],
                )
                cursor.executemany(
                    POSTGRES_EVALUATED_CONTRACT_INSERT,
                    archive_payload["evaluated_contract_values"],
                )
                cursor.executemany(
                    POSTGRES_RULE_EVALUATION_INSERT,
                    archive_payload["rule_evaluation_values"],
                )
                cursor.executemany(
                    POSTGRES_SECURITY_CHARACTERIZATION_INSERT,
                    archive_payload["security_characterization_values"],
                )
            connection.commit()

        return archive_payload["row_counts"]

    def status(self, study_id: str | None = None) -> ResearchRepositoryStatus:
        self.initialize()
        today_prefix = datetime.now(ZoneInfo("America/New_York")).date().isoformat()
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) FROM opportunity_scans")
                total_scans = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM evaluated_contracts")
                total_contracts_evaluated = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM rule_evaluations")
                total_rule_evaluations = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM security_characterization")
                total_security_characterizations = cursor.fetchone()[0]
                cursor.execute(
                    """
                    SELECT scan_id, scan_timestamp, study_id, scheduled_time_label, run_mode
                    FROM opportunity_scans
                    ORDER BY scan_timestamp DESC, scan_id DESC
                    LIMIT 1
                    """
                )
                latest = cursor.fetchone()
                latest_rows_written: dict[str, int] = {}
                if latest:
                    latest_scan_id = latest[0]
                    latest_rows_written = {}
                    for table in RESEARCH_TABLES:
                        cursor.execute(
                            f"SELECT COUNT(*) FROM {table} WHERE scan_id = %s",
                            (latest_scan_id,),
                        )
                        latest_rows_written[table] = cursor.fetchone()[0]
                cursor.execute(
                    """
                    SELECT scan_id, scan_timestamp, study_id, scheduled_time_label, run_mode
                    FROM opportunity_scans
                    WHERE scan_timestamp LIKE %s
                    ORDER BY scan_timestamp DESC, scan_id DESC
                    """,
                    (today_prefix + "%",),
                )
                today_rows = cursor.fetchall()
                cursor.execute(
                    """
                    SELECT scheduled_time_label
                    FROM opportunity_scans
                    WHERE scan_timestamp LIKE %s
                      AND run_mode = 'scheduled'
                      AND study_id = %s
                      AND scheduled_time_label IS NOT NULL
                      AND scheduled_time_label <> ''
                    """,
                    (today_prefix + "%", study_id),
                )
                progress_rows = cursor.fetchall()
                cursor.execute(
                    """
                    SELECT scan_id, scan_timestamp, study_id, scheduled_time_label, run_mode
                    FROM opportunity_scans
                    ORDER BY scan_timestamp DESC, scan_id DESC
                    LIMIT 10
                    """
                )
                recent_rows = cursor.fetchall()

        today_observations = tuple(_observation_dict(row) for row in today_rows)
        today_completed_schedule_times = tuple(
            sorted(
                {
                    normalized
                    for normalized in (
                        _normalized_schedule_time_label(row[0]) for row in progress_rows
                    )
                    if normalized
                }
            )
        )
        recent_observations = tuple(_observation_dict(row) for row in recent_rows)
        return ResearchRepositoryStatus(
            database_path=self.database_url,
            total_scans=int(total_scans or 0),
            total_contracts_evaluated=int(total_contracts_evaluated or 0),
            total_rule_evaluations=int(total_rule_evaluations or 0),
            total_security_characterizations=int(total_security_characterizations or 0),
            latest_scan_timestamp=latest[1] if latest else None,
            latest_study_id=latest[2] if latest else None,
            latest_scan_id=latest[0] if latest else None,
            latest_scheduled_time_label=latest[3] if latest else None,
            latest_run_mode=latest[4] if latest else None,
            latest_rows_written=latest_rows_written,
            today_observations=today_observations,
            today_completed_schedule_times=today_completed_schedule_times,
            recent_observations=recent_observations,
        )

    def latest_scan_row_counts(self) -> dict[str, int | str] | None:
        self.initialize()
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT scan_id
                    FROM opportunity_scans
                    ORDER BY scan_timestamp DESC, scan_id DESC
                    LIMIT 1
                    """
                )
                latest = cursor.fetchone()
                if latest is None:
                    return None
                scan_id = latest[0]
                counts: dict[str, int | str] = {"scan_id": scan_id}
                for table in RESEARCH_TABLES:
                    cursor.execute(
                        f"SELECT COUNT(*) FROM {table} WHERE scan_id = %s",
                        (scan_id,),
                    )
                    counts[table] = cursor.fetchone()[0]
        return counts

    def _connect(self):
        psycopg = _require_psycopg()
        return psycopg.connect(self.database_url)


def research_repository_target_from_env(
    env: dict[str, str] | None = None,
) -> ResearchRepositoryTarget:
    """Resolve repository configuration from environment variables."""
    env = os.environ if env is None else env
    configured_backend = env.get(RESEARCH_REPOSITORY_BACKEND_ENV, "").strip().lower()
    database_url = env.get(DATABASE_URL_ENV, "").strip() or None

    if configured_backend:
        backend = configured_backend
    elif database_url:
        backend = REPOSITORY_BACKEND_POSTGRES
    else:
        backend = REPOSITORY_BACKEND_SQLITE

    if backend == REPOSITORY_BACKEND_SQLITE:
        sqlite_path = Path(env.get(RESEARCH_SQLITE_PATH_ENV, "") or DEFAULT_RESEARCH_DB_PATH)
        return ResearchRepositoryTarget(backend=backend, sqlite_path=sqlite_path)

    if backend == REPOSITORY_BACKEND_POSTGRES:
        if not database_url:
            raise ValueError("DATABASE_URL is required when RESEARCH_REPOSITORY_BACKEND=postgres.")
        scheme = urlparse(database_url).scheme
        if scheme not in ("postgres", "postgresql"):
            raise ValueError("DATABASE_URL must use a postgres or postgresql URL scheme.")
        return ResearchRepositoryTarget(backend=backend, database_url=database_url)

    raise ValueError(
        "RESEARCH_REPOSITORY_BACKEND must be sqlite or postgres; "
        f"received {configured_backend!r}."
    )


def research_repository_from_target(target: ResearchRepositoryTarget) -> ResearchRepository:
    if target.backend == REPOSITORY_BACKEND_SQLITE:
        return SQLiteResearchRepository(target.sqlite_path or DEFAULT_RESEARCH_DB_PATH)
    if target.backend == REPOSITORY_BACKEND_POSTGRES:
        return PostgresResearchRepository(target.database_url or "")
    raise ValueError(f"Unsupported research repository backend: {target.backend}")


def research_repository_from_env(env: dict[str, str] | None = None) -> ResearchRepository:
    return research_repository_from_target(research_repository_target_from_env(env))


RESEARCH_TABLES = (
    "opportunity_scans",
    "evaluated_contracts",
    "rule_evaluations",
    "security_characterization",
)

POSTGRES_SCHEMA_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS opportunity_scans (
        scan_id TEXT PRIMARY KEY,
        scan_timestamp TEXT,
        universe_name TEXT,
        evaluation_profile_name TEXT,
        evaluation_profile_version TEXT,
        contract_quality_model_name TEXT,
        contract_quality_model_version TEXT,
        option_type TEXT,
        dte_min INTEGER,
        dte_max INTEGER,
        contracts_evaluated INTEGER,
        passing_count INTEGER,
        true_near_miss_count INTEGER,
        rejected_count INTEGER,
        average_quality_score DOUBLE PRECISION,
        median_quality_score DOUBLE PRECISION,
        highest_quality_score DOUBLE PRECISION,
        lowest_quality_score DOUBLE PRECISION,
        study_id TEXT,
        study_name TEXT,
        study_version TEXT,
        study_purpose TEXT,
        scheduled_time_label TEXT,
        run_mode TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS evaluated_contracts (
        scan_id TEXT,
        ticker TEXT,
        contract_symbol TEXT,
        option_type TEXT,
        expiration TEXT,
        strike DOUBLE PRECISION,
        dte INTEGER,
        underlying_price DOUBLE PRECISION,
        bid DOUBLE PRECISION,
        ask DOUBLE PRECISION,
        mid DOUBLE PRECISION,
        spread_pct DOUBLE PRECISION,
        delta DOUBLE PRECISION,
        open_interest INTEGER,
        volume INTEGER,
        quality_score DOUBLE PRECISION,
        classification TEXT,
        failed_rules TEXT,
        primary_strength TEXT,
        primary_weakness TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS rule_evaluations (
        scan_id TEXT,
        contract_symbol TEXT,
        ticker TEXT,
        rule_name TEXT,
        rule_weight DOUBLE PRECISION,
        actual_value TEXT,
        target TEXT,
        pass_fail_status TEXT,
        threshold_distance DOUBLE PRECISION,
        rule_score DOUBLE PRECISION,
        max_rule_score DOUBLE PRECISION
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS security_characterization (
        scan_id TEXT,
        ticker TEXT,
        contracts_evaluated INTEGER,
        passing_count INTEGER,
        true_near_miss_count INTEGER,
        rejected_count INTEGER,
        best_quality_score DOUBLE PRECISION,
        average_quality_score DOUBLE PRECISION,
        pass_rate DOUBLE PRECISION,
        near_miss_rate DOUBLE PRECISION,
        dominant_failed_rule TEXT,
        dominant_failure_signature TEXT
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_evaluated_contracts_scan ON evaluated_contracts (scan_id)",
    """
    CREATE INDEX IF NOT EXISTS idx_rule_evaluations_scan_contract
        ON rule_evaluations (scan_id, contract_symbol)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_security_characterization_scan
        ON security_characterization (scan_id)
    """,
    "ALTER TABLE opportunity_scans ADD COLUMN IF NOT EXISTS study_id TEXT",
    "ALTER TABLE opportunity_scans ADD COLUMN IF NOT EXISTS study_name TEXT",
    "ALTER TABLE opportunity_scans ADD COLUMN IF NOT EXISTS study_version TEXT",
    "ALTER TABLE opportunity_scans ADD COLUMN IF NOT EXISTS study_purpose TEXT",
    "ALTER TABLE opportunity_scans ADD COLUMN IF NOT EXISTS scheduled_time_label TEXT",
    "ALTER TABLE opportunity_scans ADD COLUMN IF NOT EXISTS run_mode TEXT",
)

POSTGRES_OPPORTUNITY_SCAN_UPSERT = """
    INSERT INTO opportunity_scans (
        scan_id, scan_timestamp, universe_name,
        evaluation_profile_name, evaluation_profile_version,
        contract_quality_model_name, contract_quality_model_version,
        option_type, dte_min, dte_max, contracts_evaluated,
        passing_count, true_near_miss_count, rejected_count,
        average_quality_score, median_quality_score, highest_quality_score,
        lowest_quality_score, study_id, study_name, study_version,
        study_purpose, scheduled_time_label, run_mode
    )
    VALUES (
        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
    )
    ON CONFLICT (scan_id) DO UPDATE SET
        scan_timestamp = EXCLUDED.scan_timestamp,
        universe_name = EXCLUDED.universe_name,
        evaluation_profile_name = EXCLUDED.evaluation_profile_name,
        evaluation_profile_version = EXCLUDED.evaluation_profile_version,
        contract_quality_model_name = EXCLUDED.contract_quality_model_name,
        contract_quality_model_version = EXCLUDED.contract_quality_model_version,
        option_type = EXCLUDED.option_type,
        dte_min = EXCLUDED.dte_min,
        dte_max = EXCLUDED.dte_max,
        contracts_evaluated = EXCLUDED.contracts_evaluated,
        passing_count = EXCLUDED.passing_count,
        true_near_miss_count = EXCLUDED.true_near_miss_count,
        rejected_count = EXCLUDED.rejected_count,
        average_quality_score = EXCLUDED.average_quality_score,
        median_quality_score = EXCLUDED.median_quality_score,
        highest_quality_score = EXCLUDED.highest_quality_score,
        lowest_quality_score = EXCLUDED.lowest_quality_score,
        study_id = EXCLUDED.study_id,
        study_name = EXCLUDED.study_name,
        study_version = EXCLUDED.study_version,
        study_purpose = EXCLUDED.study_purpose,
        scheduled_time_label = EXCLUDED.scheduled_time_label,
        run_mode = EXCLUDED.run_mode
"""

POSTGRES_EVALUATED_CONTRACT_INSERT = """
    INSERT INTO evaluated_contracts (
        scan_id, ticker, contract_symbol, option_type, expiration, strike,
        dte, underlying_price, bid, ask, mid, spread_pct, delta,
        open_interest, volume, quality_score, classification, failed_rules,
        primary_strength, primary_weakness
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
"""

POSTGRES_RULE_EVALUATION_INSERT = """
    INSERT INTO rule_evaluations (
        scan_id, contract_symbol, ticker, rule_name, rule_weight,
        actual_value, target, pass_fail_status, threshold_distance,
        rule_score, max_rule_score
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
"""

POSTGRES_SECURITY_CHARACTERIZATION_INSERT = """
    INSERT INTO security_characterization (
        scan_id, ticker, contracts_evaluated, passing_count,
        true_near_miss_count, rejected_count, best_quality_score,
        average_quality_score, pass_rate, near_miss_rate,
        dominant_failed_rule, dominant_failure_signature
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
"""


def _require_psycopg():
    try:
        import psycopg
    except ImportError as error:
        raise RuntimeError(
            "Postgres research repository requires psycopg. "
            "Install project dependencies before using RESEARCH_REPOSITORY_BACKEND=postgres."
        ) from error
    return psycopg


def initialize_research_repository(database_path: Path | str = DEFAULT_RESEARCH_DB_PATH) -> Path:
    """Create the SQLite schema used for future validation and longitudinal work."""
    path = Path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path)) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS opportunity_scans (
                scan_id TEXT PRIMARY KEY,
                scan_timestamp TEXT,
                universe_name TEXT,
                evaluation_profile_name TEXT,
                evaluation_profile_version TEXT,
                contract_quality_model_name TEXT,
                contract_quality_model_version TEXT,
                option_type TEXT,
                dte_min INTEGER,
                dte_max INTEGER,
                contracts_evaluated INTEGER,
                passing_count INTEGER,
                true_near_miss_count INTEGER,
                rejected_count INTEGER,
                average_quality_score REAL,
                median_quality_score REAL,
                highest_quality_score REAL,
                lowest_quality_score REAL
            );

            CREATE TABLE IF NOT EXISTS evaluated_contracts (
                scan_id TEXT,
                ticker TEXT,
                contract_symbol TEXT,
                option_type TEXT,
                expiration TEXT,
                strike REAL,
                dte INTEGER,
                underlying_price REAL,
                bid REAL,
                ask REAL,
                mid REAL,
                spread_pct REAL,
                delta REAL,
                open_interest INTEGER,
                volume INTEGER,
                quality_score REAL,
                classification TEXT,
                failed_rules TEXT,
                primary_strength TEXT,
                primary_weakness TEXT
            );

            CREATE TABLE IF NOT EXISTS rule_evaluations (
                scan_id TEXT,
                contract_symbol TEXT,
                ticker TEXT,
                rule_name TEXT,
                rule_weight REAL,
                actual_value TEXT,
                target TEXT,
                pass_fail_status TEXT,
                threshold_distance REAL,
                rule_score REAL,
                max_rule_score REAL
            );

            CREATE TABLE IF NOT EXISTS security_characterization (
                scan_id TEXT,
                ticker TEXT,
                contracts_evaluated INTEGER,
                passing_count INTEGER,
                true_near_miss_count INTEGER,
                rejected_count INTEGER,
                best_quality_score REAL,
                average_quality_score REAL,
                pass_rate REAL,
                near_miss_rate REAL,
                dominant_failed_rule TEXT,
                dominant_failure_signature TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_evaluated_contracts_scan
                ON evaluated_contracts (scan_id);
            CREATE INDEX IF NOT EXISTS idx_rule_evaluations_scan_contract
                ON rule_evaluations (scan_id, contract_symbol);
            CREATE INDEX IF NOT EXISTS idx_security_characterization_scan
                ON security_characterization (scan_id);
            """
        )
        _migrate_opportunity_scans_study_protocol_columns(connection)
        connection.commit()
    return path


def _migrate_opportunity_scans_study_protocol_columns(connection: sqlite3.Connection) -> None:
    existing_columns = {
        row[1] for row in connection.execute("PRAGMA table_info(opportunity_scans)").fetchall()
    }
    for column_name in (
        "study_id",
        "study_name",
        "study_version",
        "study_purpose",
        "scheduled_time_label",
        "run_mode",
    ):
        if column_name not in existing_columns:
            connection.execute(f"ALTER TABLE opportunity_scans ADD COLUMN {column_name} TEXT")
    _migrate_run_mode_values(connection)


def _migrate_run_mode_values(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        UPDATE opportunity_scans
        SET run_mode = ?
        WHERE run_mode IS NULL
           OR run_mode = ''
           OR run_mode IN ('manual', 'app-triggered')
        """,
        (RUN_MODE_MANUAL_UI,),
    )


def research_repository_status(
    database_path: Path | str = DEFAULT_RESEARCH_DB_PATH,
    study_id: str | None = None,
) -> ResearchRepositoryStatus:
    """Return current repository status without requiring the UI to know SQL."""
    path = initialize_research_repository(database_path)
    today_prefix = datetime.now(ZoneInfo("America/New_York")).date().isoformat()
    with closing(sqlite3.connect(path)) as connection:
        total_scans = connection.execute("SELECT COUNT(*) FROM opportunity_scans").fetchone()[0]
        total_contracts_evaluated = connection.execute(
            "SELECT COUNT(*) FROM evaluated_contracts"
        ).fetchone()[0]
        total_rule_evaluations = connection.execute(
            "SELECT COUNT(*) FROM rule_evaluations"
        ).fetchone()[0]
        total_security_characterizations = connection.execute(
            "SELECT COUNT(*) FROM security_characterization"
        ).fetchone()[0]
        latest = connection.execute(
            """
            SELECT scan_id, scan_timestamp, study_id, scheduled_time_label, run_mode
            FROM opportunity_scans
            ORDER BY rowid DESC
            LIMIT 1
            """
        ).fetchone()
        latest_rows_written: dict[str, int] = {}
        if latest:
            latest_scan_id = latest[0]
            latest_rows_written = {
                "opportunity_scans": connection.execute(
                    "SELECT COUNT(*) FROM opportunity_scans WHERE scan_id = ?",
                    (latest_scan_id,),
                ).fetchone()[0],
                "evaluated_contracts": connection.execute(
                    "SELECT COUNT(*) FROM evaluated_contracts WHERE scan_id = ?",
                    (latest_scan_id,),
                ).fetchone()[0],
                "rule_evaluations": connection.execute(
                    "SELECT COUNT(*) FROM rule_evaluations WHERE scan_id = ?",
                    (latest_scan_id,),
                ).fetchone()[0],
                "security_characterization": connection.execute(
                    "SELECT COUNT(*) FROM security_characterization WHERE scan_id = ?",
                    (latest_scan_id,),
                ).fetchone()[0],
            }
        today_rows = connection.execute(
            """
            SELECT scan_id, scan_timestamp, study_id, scheduled_time_label, run_mode
            FROM opportunity_scans
            WHERE scan_timestamp LIKE ?
            ORDER BY rowid DESC
            """,
            (today_prefix + "%",),
        ).fetchall()
        progress_rows = connection.execute(
            """
            SELECT scheduled_time_label
            FROM opportunity_scans
            WHERE scan_timestamp LIKE ?
              AND run_mode = 'scheduled'
              AND study_id = ?
              AND scheduled_time_label IS NOT NULL
              AND scheduled_time_label <> ''
            """,
            (today_prefix + "%", study_id),
        ).fetchall()
        recent_rows = connection.execute(
            """
            SELECT scan_id, scan_timestamp, study_id, scheduled_time_label, run_mode
            FROM opportunity_scans
            ORDER BY rowid DESC
            LIMIT 10
            """
        ).fetchall()
    today_observations = tuple(_observation_dict(row) for row in today_rows)
    today_completed_schedule_times = tuple(
        sorted(
            {
                normalized
                for normalized in (
                    _normalized_schedule_time_label(row[0]) for row in progress_rows
                )
                if normalized
            }
        )
    )
    recent_observations = tuple(_observation_dict(row) for row in recent_rows)
    return ResearchRepositoryStatus(
        database_path=str(path),
        total_scans=int(total_scans or 0),
        total_contracts_evaluated=int(total_contracts_evaluated or 0),
        total_rule_evaluations=int(total_rule_evaluations or 0),
        total_security_characterizations=int(total_security_characterizations or 0),
        latest_scan_timestamp=latest[1] if latest else None,
        latest_study_id=latest[2] if latest else None,
        latest_scan_id=latest[0] if latest else None,
        latest_scheduled_time_label=latest[3] if latest else None,
        latest_run_mode=latest[4] if latest else None,
        latest_rows_written=latest_rows_written,
        today_observations=today_observations,
        today_completed_schedule_times=today_completed_schedule_times,
        recent_observations=recent_observations,
    )


def _observation_dict(row: tuple[Any, ...]) -> dict[str, str | None]:
    return {
        "scan_id": row[0],
        "scan_timestamp": row[1],
        "study_id": row[2],
        "scheduled_time_label": row[3],
        "run_mode": row[4],
    }


def _normalized_schedule_time_label(value: Any) -> str | None:
    value = _none_if_unavailable(value)
    if value is None:
        return None
    label = str(value).strip()
    if label.upper().endswith(" ET"):
        label = label[:-3].strip()
    return label or None


def _archive_payload(
    *,
    scan_id: str,
    scan_timestamp: str,
    universe_name: str,
    option_type: str,
    dte_min: int,
    dte_max: int,
    evaluation_profile: dict[str, Any],
    evaluated_contract_rows: list[dict[str, Any]],
    contract_export_rows: list[dict[str, Any]],
    rule_export_rows: list[dict[str, Any]],
    study_protocol: dict[str, Any] | None = None,
) -> dict[str, Any]:
    summary = discovery_diagnostic_summary(evaluated_contract_rows)
    security_rows = security_characterization_rows(evaluated_contract_rows, scan_id)
    study_protocol = dict(study_protocol or {})
    study_protocol["run_mode"] = _normalized_run_mode(study_protocol.get("run_mode"))
    ticker_by_contract = {
        row.get("contract_symbol"): row.get("ticker") for row in contract_export_rows
    }
    return {
        "scan_id": scan_id,
        "opportunity_scan_values": (
            scan_id,
            scan_timestamp,
            universe_name,
            evaluation_profile.get("evaluation_profile_name"),
            evaluation_profile.get("evaluation_profile_version"),
            evaluation_profile.get("contract_quality_model_name"),
            evaluation_profile.get("contract_quality_model_version"),
            option_type,
            int(dte_min),
            int(dte_max),
            summary["Contracts Evaluated"],
            summary["Passing Contracts Count"],
            summary["True Near Miss Count"],
            summary["Rejected Count"],
            _number_or_none(summary["Average Quality Score"]),
            _number_or_none(summary["Median Quality Score"]),
            _number_or_none(summary["Highest Quality Score"]),
            _number_or_none(summary["Lowest Quality Score"]),
            study_protocol.get("study_id"),
            study_protocol.get("study_name"),
            study_protocol.get("study_version"),
            study_protocol.get("study_purpose"),
            study_protocol.get("scheduled_time_label"),
            study_protocol.get("run_mode"),
        ),
        "evaluated_contract_values": [
            _evaluated_contract_values(row) for row in contract_export_rows
        ],
        "rule_evaluation_values": [
            _rule_evaluation_values(row, ticker_by_contract.get(row.get("contract_symbol")))
            for row in rule_export_rows
        ],
        "security_characterization_values": [
            _security_characterization_values(row) for row in security_rows
        ],
        "row_counts": {
            "opportunity_scans": 1,
            "evaluated_contracts": len(contract_export_rows),
            "rule_evaluations": len(rule_export_rows),
            "security_characterization": len(security_rows),
        },
    }


def archive_opportunity_scan(
    *,
    scan_id: str,
    scan_timestamp: str,
    universe_name: str,
    option_type: str,
    dte_min: int,
    dte_max: int,
    evaluation_profile: dict[str, Any],
    evaluated_contract_rows: list[dict[str, Any]],
    contract_export_rows: list[dict[str, Any]],
    rule_export_rows: list[dict[str, Any]],
    study_protocol: dict[str, Any] | None = None,
    database_path: Path | str = DEFAULT_RESEARCH_DB_PATH,
) -> dict[str, int]:
    """Persist one completed Opportunity Discovery scan.

    Child rows for the same scan_id are replaced inside the same transaction so
    development reruns remain idempotent while normal production scan_ids stay
    append-only.
    """
    path = initialize_research_repository(database_path)
    summary = discovery_diagnostic_summary(evaluated_contract_rows)
    security_rows = security_characterization_rows(evaluated_contract_rows, scan_id)
    study_protocol = dict(study_protocol or {})
    study_protocol["run_mode"] = _normalized_run_mode(study_protocol.get("run_mode"))
    ticker_by_contract = {
        row.get("contract_symbol"): row.get("ticker") for row in contract_export_rows
    }

    with closing(sqlite3.connect(path)) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("BEGIN")
        connection.execute("DELETE FROM evaluated_contracts WHERE scan_id = ?", (scan_id,))
        connection.execute("DELETE FROM rule_evaluations WHERE scan_id = ?", (scan_id,))
        connection.execute("DELETE FROM security_characterization WHERE scan_id = ?", (scan_id,))
        connection.execute(
            """
            INSERT OR REPLACE INTO opportunity_scans (
                scan_id, scan_timestamp, universe_name,
                evaluation_profile_name, evaluation_profile_version,
                contract_quality_model_name, contract_quality_model_version,
                option_type, dte_min, dte_max, contracts_evaluated,
                passing_count, true_near_miss_count, rejected_count,
                average_quality_score, median_quality_score, highest_quality_score,
                lowest_quality_score, study_id, study_name, study_version,
                study_purpose, scheduled_time_label, run_mode
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                scan_id,
                scan_timestamp,
                universe_name,
                evaluation_profile.get("evaluation_profile_name"),
                evaluation_profile.get("evaluation_profile_version"),
                evaluation_profile.get("contract_quality_model_name"),
                evaluation_profile.get("contract_quality_model_version"),
                option_type,
                int(dte_min),
                int(dte_max),
                summary["Contracts Evaluated"],
                summary["Passing Contracts Count"],
                summary["True Near Miss Count"],
                summary["Rejected Count"],
                _number_or_none(summary["Average Quality Score"]),
                _number_or_none(summary["Median Quality Score"]),
                _number_or_none(summary["Highest Quality Score"]),
                _number_or_none(summary["Lowest Quality Score"]),
                study_protocol.get("study_id"),
                study_protocol.get("study_name"),
                study_protocol.get("study_version"),
                study_protocol.get("study_purpose"),
                study_protocol.get("scheduled_time_label"),
                study_protocol.get("run_mode"),
            ),
        )
        connection.executemany(
            """
            INSERT INTO evaluated_contracts (
                scan_id, ticker, contract_symbol, option_type, expiration, strike,
                dte, underlying_price, bid, ask, mid, spread_pct, delta,
                open_interest, volume, quality_score, classification, failed_rules,
                primary_strength, primary_weakness
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [_evaluated_contract_values(row) for row in contract_export_rows],
        )
        connection.executemany(
            """
            INSERT INTO rule_evaluations (
                scan_id, contract_symbol, ticker, rule_name, rule_weight,
                actual_value, target, pass_fail_status, threshold_distance,
                rule_score, max_rule_score
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                _rule_evaluation_values(row, ticker_by_contract.get(row.get("contract_symbol")))
                for row in rule_export_rows
            ],
        )
        connection.executemany(
            """
            INSERT INTO security_characterization (
                scan_id, ticker, contracts_evaluated, passing_count,
                true_near_miss_count, rejected_count, best_quality_score,
                average_quality_score, pass_rate, near_miss_rate,
                dominant_failed_rule, dominant_failure_signature
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [_security_characterization_values(row) for row in security_rows],
        )
        connection.commit()

    return {
        "opportunity_scans": 1,
        "evaluated_contracts": len(contract_export_rows),
        "rule_evaluations": len(rule_export_rows),
        "security_characterization": len(security_rows),
    }


def latest_scan_row_counts(
    database_path: Path | str = DEFAULT_RESEARCH_DB_PATH,
) -> dict[str, int | str] | None:
    """Return row counts for the most recently archived scan."""
    path = initialize_research_repository(database_path)
    with closing(sqlite3.connect(path)) as connection:
        latest = connection.execute(
            """
            SELECT scan_id
            FROM opportunity_scans
            ORDER BY rowid DESC
            LIMIT 1
            """
        ).fetchone()
        if latest is None:
            return None
        scan_id = latest[0]
        counts: dict[str, int | str] = {"scan_id": scan_id}
        for table in (
            "opportunity_scans",
            "evaluated_contracts",
            "rule_evaluations",
            "security_characterization",
        ):
            counts[table] = connection.execute(
                f"SELECT COUNT(*) FROM {table} WHERE scan_id = ?", (scan_id,)
            ).fetchone()[0]
    return counts


def _normalized_run_mode(value: Any) -> str:
    if value is None or value == "":
        return RUN_MODE_MANUAL_UI
    run_mode = str(value)
    run_mode = LEGACY_RUN_MODE_MAP.get(run_mode, run_mode)
    if run_mode not in CANONICAL_RUN_MODES:
        raise ValueError(f"Unsupported run_mode: {value}")
    return run_mode


def security_characterization_rows(
    rows: list[dict[str, Any]], scan_id: str
) -> list[dict[str, Any]]:
    """Aggregate one row per ticker for later security-level validation research."""
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        ticker = str(row.get("Ticker") or "").strip().upper()
        if ticker:
            grouped[ticker].append(row)

    return [
        _security_characterization_row(scan_id, ticker, ticker_rows)
        for ticker, ticker_rows in sorted(grouped.items())
    ]


def _security_characterization_row(
    scan_id: str, ticker: str, rows: list[dict[str, Any]]
) -> dict[str, Any]:
    passing_count = sum(row.get("All Passed") == ALL_PASSED_YES for row in rows)
    true_near_miss_count = len(near_miss_contracts(rows))
    rejected_count = max(len(rows) - passing_count - true_near_miss_count, 0)
    scores = [_number for _number in (_number_or_none(row.get("Quality Score")) for row in rows) if _number is not None]
    failed_rule_counter: Counter[str] = Counter()
    signature_counter: Counter[str] = Counter()
    for row in rows:
        failed_rules = _failed_rules_for_row(row)
        failed_rule_counter.update(failed_rules)
        if failed_rules:
            signature_counter.update([", ".join(failed_rules)])

    total = len(rows)
    return {
        "scan_id": scan_id,
        "ticker": ticker,
        "contracts_evaluated": total,
        "passing_count": passing_count,
        "true_near_miss_count": true_near_miss_count,
        "rejected_count": rejected_count,
        "best_quality_score": max(scores) if scores else None,
        "average_quality_score": mean(scores) if scores else None,
        "pass_rate": passing_count / total if total else None,
        "near_miss_rate": true_near_miss_count / total if total else None,
        "dominant_failed_rule": _most_common_label(failed_rule_counter),
        "dominant_failure_signature": _most_common_label(signature_counter),
    }


def _failed_rules_for_row(row: dict[str, Any]) -> list[str]:
    labels = {
        "Delta Fit": "Delta",
        "Spread Pass": "Spread",
        "Open Interest Pass": "Open Interest",
        "Volume Pass": "Volume",
    }
    return [labels[check] for check in QUALITY_CHECKS if row.get(check) == FAIL]


def _most_common_label(counter: Counter[str]) -> str | None:
    if not counter:
        return None
    highest_count = max(counter.values())
    return ", ".join(sorted(label for label, count in counter.items() if count == highest_count))


def _evaluated_contract_values(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        row.get("scan_id"),
        row.get("ticker"),
        row.get("contract_symbol"),
        row.get("option_type"),
        _none_if_unavailable(row.get("expiration")),
        _number_or_none(row.get("strike")),
        _integer_or_none(row.get("dte")),
        _number_or_none(row.get("underlying_price")),
        _number_or_none(row.get("bid")),
        _number_or_none(row.get("ask")),
        _number_or_none(row.get("mid")),
        _number_or_none(row.get("spread_pct")),
        _number_or_none(row.get("delta")),
        _integer_or_none(row.get("open_interest")),
        _integer_or_none(row.get("volume")),
        _number_or_none(row.get("quality_score")),
        row.get("classification"),
        _none_if_unavailable(row.get("failed_rules")),
        _none_if_unavailable(row.get("primary_strength")),
        _none_if_unavailable(row.get("primary_weakness")),
    )


def _rule_evaluation_values(row: dict[str, Any], ticker: str | None) -> tuple[Any, ...]:
    return (
        row.get("scan_id"),
        row.get("contract_symbol"),
        ticker,
        row.get("rule_name"),
        _number_or_none(row.get("rule_weight")),
        _text_or_none(row.get("actual_value")),
        _text_or_none(row.get("target")),
        row.get("pass_fail_status"),
        _number_or_none(row.get("threshold_distance")),
        _number_or_none(row.get("rule_score")),
        _number_or_none(row.get("max_rule_score")),
    )


def _security_characterization_values(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        row.get("scan_id"),
        row.get("ticker"),
        row.get("contracts_evaluated"),
        row.get("passing_count"),
        row.get("true_near_miss_count"),
        row.get("rejected_count"),
        _number_or_none(row.get("best_quality_score")),
        _number_or_none(row.get("average_quality_score")),
        _number_or_none(row.get("pass_rate")),
        _number_or_none(row.get("near_miss_rate")),
        row.get("dominant_failed_rule"),
        row.get("dominant_failure_signature"),
    )


def _none_if_unavailable(value: Any) -> Any:
    if value in (None, "", "-", "N/A"):
        return None
    return value


def _text_or_none(value: Any) -> str | None:
    value = _none_if_unavailable(value)
    return None if value is None else str(value)


def _number_or_none(value: Any) -> float | None:
    value = _none_if_unavailable(value)
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if isfinite(number) else None


def _integer_or_none(value: Any) -> int | None:
    number = _number_or_none(value)
    return None if number is None else int(number)
