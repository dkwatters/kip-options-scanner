"""Versioned QA benchmark storage for the Research Conversation Engine.

This module is deliberately independent from Research Universe and production
research persistence.  It imports only human-reviewed canonical JSON artifacts.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from collections import Counter
from contextlib import closing
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


DEFAULT_BENCHMARK_DB_PATH = Path("data/research/rce_benchmarks.sqlite")
EXPECTED_STATUSES = {"core", "adjacent", "optional", "excluded"}
EXPECTATIONS = {
    "must_include", "should_include", "acceptable", "must_exclude",
    "private_reference", "international_reference", "fund_reference",
}
PUBLIC_STATUSES = {"public", "private", "acquired", "delisted", "unknown"}
REQUIRED_METADATA = {
    "benchmark_id", "benchmark_name", "research_question", "description",
    "domain", "difficulty", "benchmark_status", "version", "source_document",
    "source_date", "reviewed_by", "review_notes",
}


class BenchmarkValidationError(ValueError):
    """A canonical fixture does not satisfy the benchmark contract."""


class DuplicateBenchmarkError(ValueError):
    """The same benchmark identifier and version already exists."""


@dataclass(slots=True)
class ImportReport:
    fixtures: int = 0
    benchmarks: int = 0
    categories: int = 0
    securities: int = 0
    sources: int = 0
    dry_run: bool = True
    duplicate_tickers: list[str] = field(default_factory=list)
    missing_security_identifiers: list[str] = field(default_factory=list)
    special_references: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "fixtures": self.fixtures, "benchmarks": self.benchmarks,
            "categories": self.categories, "securities": self.securities,
            "sources": self.sources, "dry_run": self.dry_run,
            "duplicate_tickers": self.duplicate_tickers,
            "missing_security_identifiers": self.missing_security_identifiers,
            "special_references": self.special_references,
        }


SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS rce_benchmark (
    benchmark_id TEXT NOT NULL,
    benchmark_name TEXT NOT NULL,
    research_question TEXT NOT NULL,
    description TEXT NOT NULL,
    domain TEXT NOT NULL,
    difficulty TEXT NOT NULL,
    benchmark_status TEXT NOT NULL,
    version TEXT NOT NULL,
    source_document TEXT NOT NULL,
    source_date TEXT,
    reviewed_by TEXT NOT NULL,
    review_notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (benchmark_id, version)
);
CREATE TABLE IF NOT EXISTS rce_benchmark_category (
    benchmark_category_id TEXT PRIMARY KEY,
    benchmark_id TEXT NOT NULL,
    benchmark_version TEXT NOT NULL,
    category_name TEXT NOT NULL,
    category_role TEXT NOT NULL,
    importance INTEGER NOT NULL,
    expected_status TEXT NOT NULL CHECK (expected_status IN ('core','adjacent','optional','excluded')),
    notes TEXT,
    FOREIGN KEY (benchmark_id, benchmark_version)
      REFERENCES rce_benchmark (benchmark_id, version) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS rce_benchmark_security (
    benchmark_security_id TEXT PRIMARY KEY,
    benchmark_id TEXT NOT NULL,
    benchmark_version TEXT NOT NULL,
    ticker TEXT,
    company_name TEXT,
    reference_identifier TEXT,
    exchange TEXT,
    listing_region TEXT,
    public_status TEXT NOT NULL CHECK (public_status IN ('public','private','acquired','delisted','unknown')),
    category_name TEXT NOT NULL,
    expectation TEXT NOT NULL CHECK (expectation IN ('must_include','should_include','acceptable','must_exclude','private_reference','international_reference','fund_reference')),
    importance INTEGER NOT NULL,
    role_summary TEXT NOT NULL,
    evidence_summary TEXT NOT NULL,
    notes TEXT,
    FOREIGN KEY (benchmark_id, benchmark_version)
      REFERENCES rce_benchmark (benchmark_id, version) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS rce_benchmark_source (
    benchmark_source_id TEXT PRIMARY KEY,
    benchmark_id TEXT NOT NULL,
    benchmark_version TEXT NOT NULL,
    source_document TEXT NOT NULL,
    source_page TEXT,
    source_section TEXT,
    source_date TEXT,
    source_notes TEXT,
    source_hash TEXT NOT NULL,
    FOREIGN KEY (benchmark_id, benchmark_version)
      REFERENCES rce_benchmark (benchmark_id, version) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_rce_benchmark_security_ticker
  ON rce_benchmark_security (ticker);
CREATE INDEX IF NOT EXISTS idx_rce_benchmark_source_hash
  ON rce_benchmark_source (source_hash);
"""


def _text(value: Any, label: str, *, optional: bool = False) -> str | None:
    if value is None and optional:
        return None
    if not isinstance(value, str) or not value.strip():
        raise BenchmarkValidationError(f"{label} must be a non-empty string")
    return value.strip()


def validate_fixture(document: Any, *, filename: str = "<fixture>") -> dict[str, Any]:
    if not isinstance(document, dict):
        raise BenchmarkValidationError(f"{filename}: fixture root must be an object")
    if document.get("schema_version") != "1.0":
        raise BenchmarkValidationError(f"{filename}: schema_version must be '1.0'")
    metadata = document.get("benchmark")
    if not isinstance(metadata, dict):
        raise BenchmarkValidationError(f"{filename}: benchmark must be an object")
    missing = sorted(REQUIRED_METADATA - metadata.keys())
    if missing:
        raise BenchmarkValidationError(f"{filename}: missing benchmark fields: {', '.join(missing)}")
    for key in REQUIRED_METADATA:
        _text(metadata[key], f"{filename}: benchmark.{key}", optional=key == "source_date")
    for array_name in ("categories", "securities", "sources", "benchmark_caveats"):
        if not isinstance(document.get(array_name), list):
            raise BenchmarkValidationError(f"{filename}: {array_name} must be an array")
    if not document["categories"] or not document["sources"]:
        raise BenchmarkValidationError(f"{filename}: categories and sources cannot be empty")
    category_names: set[str] = set()
    for index, row in enumerate(document["categories"]):
        label = f"{filename}: categories[{index}]"
        if not isinstance(row, dict):
            raise BenchmarkValidationError(f"{label} must be an object")
        for key in ("category_name", "category_role", "notes"):
            _text(row.get(key), f"{label}.{key}", optional=key == "notes")
        if row.get("expected_status") not in EXPECTED_STATUSES:
            raise BenchmarkValidationError(f"{label}.expected_status is invalid")
        if not isinstance(row.get("importance"), int) or not 1 <= row["importance"] <= 5:
            raise BenchmarkValidationError(f"{label}.importance must be an integer from 1 to 5")
        if row["category_name"] in category_names:
            raise BenchmarkValidationError(f"{label}: duplicate category_name")
        category_names.add(row["category_name"])
    for index, row in enumerate(document["securities"]):
        label = f"{filename}: securities[{index}]"
        if not isinstance(row, dict):
            raise BenchmarkValidationError(f"{label} must be an object")
        if row.get("expectation") not in EXPECTATIONS:
            raise BenchmarkValidationError(f"{label}.expectation is invalid")
        if row.get("public_status") not in PUBLIC_STATUSES:
            raise BenchmarkValidationError(f"{label}.public_status is invalid")
        if row.get("category_name") not in category_names:
            raise BenchmarkValidationError(f"{label}.category_name is not declared")
        if not isinstance(row.get("importance"), int) or not 1 <= row["importance"] <= 5:
            raise BenchmarkValidationError(f"{label}.importance must be an integer from 1 to 5")
        for key in ("role_summary", "evidence_summary"):
            _text(row.get(key), f"{label}.{key}")
        for key in (
            "ticker", "company_name", "reference_identifier", "exchange", "listing_region", "notes"
        ):
            value = row.get(key)
            if value is not None and not isinstance(value, str):
                raise BenchmarkValidationError(f"{label}.{key} must be a string or null")
    for index, row in enumerate(document["sources"]):
        label = f"{filename}: sources[{index}]"
        if not isinstance(row, dict):
            raise BenchmarkValidationError(f"{label} must be an object")
        for key in ("source_document", "source_hash"):
            _text(row.get(key), f"{label}.{key}")
        if len(row["source_hash"]) != 64 or any(c not in "0123456789abcdef" for c in row["source_hash"].lower()):
            raise BenchmarkValidationError(f"{label}.source_hash must be a SHA-256 hex digest")
    return document


def load_fixture(path: Path | str) -> dict[str, Any]:
    fixture_path = Path(path)
    try:
        payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BenchmarkValidationError(f"{fixture_path}: {exc}") from exc
    return validate_fixture(payload, filename=fixture_path.name)


def load_fixture_directory(path: Path | str) -> list[dict[str, Any]]:
    directory = Path(path)
    fixtures = [load_fixture(item) for item in sorted(directory.glob("*.json"))]
    if not fixtures:
        raise BenchmarkValidationError(f"No JSON fixtures found in {directory}")
    identities: set[tuple[str, str]] = set()
    source_owners: dict[str, tuple[str, str]] = {}
    for fixture in fixtures:
        metadata = fixture["benchmark"]
        identity = (metadata["benchmark_id"], metadata["version"])
        if identity in identities:
            raise BenchmarkValidationError(f"Duplicate benchmark/version in fixtures: {identity}")
        identities.add(identity)
        source_key = metadata["source_document"].strip().casefold()
        prior = source_owners.get(source_key)
        if prior and prior != identity:
            raise BenchmarkValidationError(
                f"Duplicate source document defines multiple benchmarks: {metadata['source_document']}"
            )
        source_owners[source_key] = identity
    return fixtures


def initialize_benchmark_repository(database_path: Path | str = DEFAULT_BENCHMARK_DB_PATH) -> Path:
    path = Path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path)) as connection:
        connection.executescript(SCHEMA)
        security_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(rce_benchmark_security)")
        }
        if "reference_identifier" not in security_columns:
            connection.execute(
                "ALTER TABLE rce_benchmark_security ADD COLUMN reference_identifier TEXT"
            )
        connection.commit()
    return path


def _row_id(kind: str, benchmark_id: str, version: str, index: int) -> str:
    return hashlib.sha256(f"{kind}|{benchmark_id}|{version}|{index}".encode()).hexdigest()[:32]


def import_fixtures(
    fixtures: Iterable[dict[str, Any]], *, database_path: Path | str = DEFAULT_BENCHMARK_DB_PATH,
    apply: bool = False,
) -> ImportReport:
    documents = [validate_fixture(item) for item in fixtures]
    report = ImportReport(fixtures=len(documents), dry_run=not apply)
    all_tickers: list[str] = []
    for document in documents:
        report.benchmarks += 1
        report.categories += len(document["categories"])
        report.securities += len(document["securities"])
        report.sources += len(document["sources"])
        benchmark_id = document["benchmark"]["benchmark_id"]
        for index, security in enumerate(document["securities"]):
            ticker = (security.get("ticker") or "").strip().upper()
            company = (security.get("company_name") or "").strip()
            if ticker:
                all_tickers.append(ticker)
            reference_identifier = (security.get("reference_identifier") or "").strip()
            is_non_ticker_reference = (
                security["expectation"] == "private_reference"
                and security["public_status"] in {"private", "acquired", "delisted"}
            )
            identifier_is_missing = (
                not company
                or (is_non_ticker_reference and not (ticker or reference_identifier))
                or (not is_non_ticker_reference and not ticker)
            )
            if identifier_is_missing:
                report.missing_security_identifiers.append(f"{benchmark_id}:security[{index}]")
            if security["expectation"] in {
                "private_reference", "international_reference", "fund_reference"
            }:
                report.special_references.append(
                    f"{benchmark_id}:{ticker or company}:{security['expectation']}"
                )
    report.duplicate_tickers = sorted(
        ticker for ticker, count in Counter(all_tickers).items() if count > 1
    )

    path = Path(database_path)
    if not apply:
        if path.exists():
            with closing(sqlite3.connect(f"file:{path.resolve().as_posix()}?mode=ro", uri=True)) as connection:
                table_exists = connection.execute(
                    "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'rce_benchmark'"
                ).fetchone()
                if table_exists:
                    for document in documents:
                        metadata = document["benchmark"]
                        identity = (metadata["benchmark_id"], metadata["version"])
                        if connection.execute(
                            "SELECT 1 FROM rce_benchmark WHERE benchmark_id = ? AND version = ?",
                            identity,
                        ).fetchone():
                            raise DuplicateBenchmarkError(
                                f"Benchmark/version already imported: {identity[0]} {identity[1]}"
                            )
        return report

    path = initialize_benchmark_repository(path)
    now = datetime.now(timezone.utc).isoformat()
    with closing(sqlite3.connect(path)) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            connection.execute("BEGIN")
            for document in documents:
                metadata = document["benchmark"]
                identity = (metadata["benchmark_id"], metadata["version"])
                if connection.execute(
                    "SELECT 1 FROM rce_benchmark WHERE benchmark_id = ? AND version = ?", identity
                ).fetchone():
                    raise DuplicateBenchmarkError(f"Benchmark/version already imported: {identity[0]} {identity[1]}")
                connection.execute(
                    "INSERT INTO rce_benchmark VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (*[metadata[key] for key in (
                        "benchmark_id", "benchmark_name", "research_question", "description",
                        "domain", "difficulty", "benchmark_status", "version", "source_document",
                        "source_date", "reviewed_by", "review_notes")], now, now),
                )
                for index, row in enumerate(document["categories"]):
                    connection.execute(
                        "INSERT INTO rce_benchmark_category VALUES (?,?,?,?,?,?,?,?)",
                        (_row_id("category", *identity, index), *identity, row["category_name"],
                         row["category_role"], row["importance"], row["expected_status"], row.get("notes")),
                    )
                for index, row in enumerate(document["securities"]):
                    connection.execute(
                        """INSERT INTO rce_benchmark_security (
                            benchmark_security_id, benchmark_id, benchmark_version, ticker,
                            company_name, reference_identifier, exchange, listing_region,
                            public_status, category_name, expectation, importance, role_summary,
                            evidence_summary, notes
                        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (_row_id("security", *identity, index), *identity,
                         row.get("ticker"), row.get("company_name"), row.get("reference_identifier"),
                         row.get("exchange"),
                         row.get("listing_region"), row["public_status"], row["category_name"],
                         row["expectation"], row["importance"], row["role_summary"],
                         row["evidence_summary"], row.get("notes")),
                    )
                for index, row in enumerate(document["sources"]):
                    connection.execute(
                        "INSERT INTO rce_benchmark_source VALUES (?,?,?,?,?,?,?,?,?)",
                        (_row_id("source", *identity, index), *identity, row["source_document"],
                         row.get("source_page"), row.get("source_section"), row.get("source_date"),
                         row.get("source_notes"), row["source_hash"].lower()),
                    )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
    return report


def import_fixture_directory(
    fixture_path: Path | str, *, database_path: Path | str = DEFAULT_BENCHMARK_DB_PATH,
    apply: bool = False,
) -> ImportReport:
    return import_fixtures(load_fixture_directory(fixture_path), database_path=database_path, apply=apply)
