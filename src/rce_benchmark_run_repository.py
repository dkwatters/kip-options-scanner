"""Persistence and human-review operations for benchmark-only RCE runs."""
from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.rce_benchmark_metrics import REVIEW_STATUSES
from src.rce_benchmark_repository import DEFAULT_BENCHMARK_DB_PATH, initialize_benchmark_repository


REVIEW_DIMENSIONS = {
    "interpretation_quality", "research_map_quality", "scope_quality", "evidence_quality",
    "margin_research_quality", "explainability", "overall_analyst_usefulness",
}


def utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def persist_run(
    run: dict[str, Any], *, database_path: Path | str = DEFAULT_BENCHMARK_DB_PATH,
) -> None:
    initialize_benchmark_repository(database_path)
    metric_version = run["scoring_config"]["metric_version"]
    weights = run["scoring_config"]["overall_weights"]
    with closing(sqlite3.connect(database_path)) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            connection.execute("BEGIN")
            connection.execute(
                """INSERT INTO rce_benchmark_run (
                    benchmark_run_id, benchmark_id, benchmark_version, run_label, provider,
                    model, prompt_version, scoring_config_version, run_timestamp, latency_seconds, input_tokens,
                    cached_input_tokens, output_tokens, reasoning_tokens, estimated_cost,
                    raw_candidate_count, parsed_candidate_count, verified_candidate_count,
                    run_status, schema_valid, provider_verification_valid, fallback_used,
                    error_type, error_message, raw_response_path, parsed_artifact_path,
                    overall_score, parser_warnings
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    run["benchmark_run_id"], run["benchmark_id"], run["benchmark_version"],
                    run["run_label"], run["provider"], run["model"], run["prompt_version"],
                    run["scoring_config"]["config_version"], run["run_timestamp"],
                    run.get("latency_seconds"), run["usage"].get("input"),
                    run["usage"].get("cached_input"), run["usage"].get("output"),
                    run["usage"].get("reasoning"), run.get("estimated_cost"),
                    run.get("raw_candidate_count", 0), run.get("parsed_candidate_count", 0),
                    run.get("verified_candidate_count", 0), run["run_status"],
                    int(run["schema_valid"]), int(run["provider_verification_valid"]),
                    int(run["fallback_used"]), run.get("error_type"), run.get("error_message"),
                    run.get("raw_response_path"), run.get("parsed_artifact_path"),
                    run.get("overall_score"), json.dumps(run.get("parser_warnings", [])),
                ),
            )
            evaluation = run.get("evaluation", {})
            for name, value in evaluation.get("metrics", {}).items():
                connection.execute(
                    "INSERT INTO rce_benchmark_metric VALUES (?,?,?,?,?,?)",
                    (run["benchmark_run_id"], name, value, weights.get(name, 0.0), metric_version,
                     evaluation.get("metric_notes", {}).get(name)),
                )
            for row in evaluation.get("candidate_results", []):
                connection.execute(
                    """INSERT INTO rce_benchmark_candidate_result (
                        benchmark_run_id,ticker,company_name,returned,returned_rank,
                        expected_classification,expected_category,returned_category,category_match,
                        rationale_present,evidence_present,listing_valid,public_status_valid,
                        validation_status,comparison_outcome,reviewer_status,reviewer_notes
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (run["benchmark_run_id"], row.get("ticker"), row.get("company_name"),
                     int(row["returned"]), row.get("returned_rank"), row.get("expected_classification"),
                     row.get("expected_category"), row.get("returned_category"), int(row["category_match"]),
                     int(row["rationale_present"]), int(row["evidence_present"]), int(row["listing_valid"]),
                     int(row["public_status_valid"]), row.get("validation_status"),
                     row["comparison_outcome"], row.get("reviewer_status"), row.get("reviewer_notes")),
                )
            for row in evaluation.get("category_results", []):
                connection.execute(
                    "INSERT INTO rce_benchmark_category_result VALUES (?,?,?,?,?,?,?)",
                    (run["benchmark_run_id"], row["category_name"], row["expected_status"],
                     row["importance"], int(row["returned"]), row["coverage_credit"], row.get("notes")),
                )
            connection.commit()
        except Exception:
            connection.rollback()
            raise


def list_unresolved_candidates(database_path: Path | str = DEFAULT_BENCHMARK_DB_PATH) -> list[dict[str, Any]]:
    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """SELECT c.candidate_result_id,c.benchmark_run_id,r.benchmark_id,c.ticker,c.company_name,
                      c.returned_category,c.reviewer_status,c.reviewer_notes
               FROM rce_benchmark_candidate_result c JOIN rce_benchmark_run r USING (benchmark_run_id)
               WHERE c.comparison_outcome='unexpected_candidate'
                 AND (c.reviewer_status IS NULL OR c.reviewer_status='needs_verification')
               ORDER BY r.run_timestamp,c.returned_rank"""
        ).fetchall()
    return [dict(row) for row in rows]


def review_candidate(
    candidate_result_id: int, status: str, reviewer: str, notes: str = "", *,
    database_path: Path | str = DEFAULT_BENCHMARK_DB_PATH,
) -> str:
    if status not in REVIEW_STATUSES:
        raise ValueError(f"reviewer status must be one of: {', '.join(sorted(REVIEW_STATUSES))}")
    now = utc_iso()
    review_id = uuid.uuid4().hex
    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        candidate = connection.execute(
            "SELECT * FROM rce_benchmark_candidate_result WHERE candidate_result_id=?",
            (candidate_result_id,),
        ).fetchone()
        if candidate is None or candidate["comparison_outcome"] != "unexpected_candidate":
            raise ValueError("candidate_result_id is not an unexpected benchmark candidate")
        connection.execute(
            "UPDATE rce_benchmark_candidate_result SET reviewer_status=?,reviewer_notes=? WHERE candidate_result_id=?",
            (status, notes, candidate_result_id),
        )
        connection.execute(
            "INSERT INTO rce_benchmark_review_audit (review_id,benchmark_run_id,review_dimension,score,reviewer,review_status,notes,recorded_at) VALUES (?,?,?,?,?,?,?,?)",
            (review_id, candidate["benchmark_run_id"], "unexpected_candidate", None, reviewer, status, notes, now),
        )
        connection.commit()
    return review_id


def record_qualitative_review(
    benchmark_run_id: str, dimension: str, score: float, reviewer: str,
    review_status: str = "completed", notes: str = "", *,
    database_path: Path | str = DEFAULT_BENCHMARK_DB_PATH,
) -> str:
    if dimension not in REVIEW_DIMENSIONS:
        raise ValueError(f"unsupported review dimension: {dimension}")
    if not 0 <= score <= 1:
        raise ValueError("qualitative score must be between 0 and 1")
    review_id, now = uuid.uuid4().hex, utc_iso()
    with closing(sqlite3.connect(database_path)) as connection:
        connection.execute(
            "INSERT INTO rce_benchmark_human_review VALUES (?,?,?,?,?,?,?,?,?)",
            (review_id, benchmark_run_id, dimension, score, reviewer, review_status, notes, now, now),
        )
        connection.execute(
            "INSERT INTO rce_benchmark_review_audit (review_id,benchmark_run_id,review_dimension,score,reviewer,review_status,notes,recorded_at) VALUES (?,?,?,?,?,?,?,?)",
            (review_id, benchmark_run_id, dimension, score, reviewer, review_status, notes, now),
        )
        connection.commit()
    return review_id


def load_runs(selector: str, database_path: Path | str = DEFAULT_BENCHMARK_DB_PATH) -> list[dict[str, Any]]:
    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        if selector == "latest":
            label_row = connection.execute("SELECT run_label FROM rce_benchmark_run ORDER BY run_timestamp DESC LIMIT 1").fetchone()
            if not label_row:
                return []
            selector = label_row[0]
        rows = connection.execute(
            "SELECT * FROM rce_benchmark_run WHERE run_label=? OR benchmark_run_id=? ORDER BY benchmark_id,run_timestamp",
            (selector, selector),
        ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            metrics = connection.execute(
                """SELECT metric_name,metric_value FROM rce_benchmark_metric
                   WHERE benchmark_run_id=? ORDER BY metric_name""",
                (row["benchmark_run_id"],),
            ).fetchall()
            item["metrics"] = {metric[0]: metric[1] for metric in metrics}
            item["candidates"] = [dict(candidate) for candidate in connection.execute(
                """SELECT * FROM rce_benchmark_candidate_result WHERE benchmark_run_id=?
                   ORDER BY
                     CASE comparison_outcome
                       WHEN 'expected_returned' THEN 0
                       WHEN 'expected_missing' THEN 1
                       WHEN 'must_exclude_returned' THEN 2
                       WHEN 'unexpected_candidate' THEN 3
                       ELSE 4
                     END,
                     CASE WHEN returned_rank IS NULL THEN 1 ELSE 0 END,
                     returned_rank,
                     COALESCE(ticker, ''),
                     COALESCE(company_name, ''),
                     candidate_result_id""",
                (row["benchmark_run_id"],),
            ).fetchall()]
            item["categories"] = [dict(category) for category in connection.execute(
                """SELECT * FROM rce_benchmark_category_result WHERE benchmark_run_id=?
                   ORDER BY category_name""",
                (row["benchmark_run_id"],),
            ).fetchall()]
            result.append(item)
    return result
