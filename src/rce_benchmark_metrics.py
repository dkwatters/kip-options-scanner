"""Deterministic, versioned scoring for RCE benchmark artifacts.

Unexpected candidates are deliberately retained as unresolved discoveries.  They
are not classified as incorrect unless a human reviews them or an explicit
fixture constraint can be evaluated deterministically.
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_SCORING_CONFIG_PATH = Path("config/rce_benchmark_scoring_v0.1.json")
REVIEW_STATUSES = {
    "valid_novel_discovery", "weak_but_relevant", "out_of_scope", "incorrect",
    "needs_verification",
}


def load_scoring_config(path: Path | str = DEFAULT_SCORING_CONFIG_PATH) -> dict[str, Any]:
    config = json.loads(Path(path).read_text(encoding="utf-8"))
    weights = config.get("overall_weights", {})
    if not weights or abs(sum(float(value) for value in weights.values()) - 1.0) > 1e-9:
        raise ValueError("overall_weights must exist and sum to 1.0")
    return config


def _key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").casefold()).strip()


def _ticker(candidate: dict[str, Any]) -> str:
    return str(candidate.get("ticker") or "").strip().upper()


def candidate_identity(candidate: dict[str, Any]) -> str:
    return _ticker(candidate) or _key(candidate.get("company_name"))


def _expected_identity(security: dict[str, Any]) -> str:
    return str(security.get("ticker") or "").strip().upper() or _key(
        security.get("company_name") or security.get("reference_identifier")
    )


def _returned_candidates(artifact: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = artifact.get("candidate_securities")
    if not isinstance(candidates, list):
        universe = artifact.get("proposed_research_universe")
        candidates = universe.get("candidate_securities") if isinstance(universe, dict) else []
    return [row for row in candidates if isinstance(row, dict)] if isinstance(candidates, list) else []


def _evidence_present(candidate: dict[str, Any]) -> bool:
    fields = ("evidence", "evidence_summary", "sources", "citations")
    return any(candidate.get(field) not in (None, "", [], {}) for field in fields)


def _artifact_supports_evidence(candidates: list[dict[str, Any]]) -> bool:
    return any(any(field in row for field in ("evidence", "evidence_summary", "sources", "citations")) for row in candidates)


def _category_names(artifact: dict[str, Any], candidates: list[dict[str, Any]]) -> set[str]:
    names = {
        _key(row.get("returned_category") or row.get("category") or row.get("subdomain"))
        for row in candidates
    }
    research_map = artifact.get("research_map")
    if isinstance(research_map, list):
        names.update(_key(row.get("area")) for row in research_map if isinstance(row, dict))
    return {name for name in names if name}


def _listing_violation(candidate: dict[str, Any], expected: dict[str, Any] | None) -> str | None:
    validation = str(candidate.get("entity_validation_status") or "").casefold()
    if validation and validation != "valid":
        return "candidate_entity_validation"
    if expected is None:
        # The current RCE artifact has no authoritative listing/public-status fields.
        return None
    expectation = expected.get("expectation")
    category_status = expected.get("_category_status")
    if category_status == "excluded" or expectation == "must_exclude":
        return None  # scored by dedicated exclusion metrics
    if expected.get("public_status") in {"private", "acquired", "delisted"} and not expected.get("_reference_permitted"):
        return "non_public_investable_candidate"
    if expectation == "fund_reference" and not expected.get("_reference_permitted"):
        return "fund_investable_candidate"
    if expectation == "international_reference" and not expected.get("_reference_permitted"):
        return "international_security_constraint"
    return None


@dataclass(slots=True)
class EvaluationResult:
    metrics: dict[str, float]
    metric_notes: dict[str, str]
    candidate_results: list[dict[str, Any]]
    category_results: list[dict[str, Any]]
    overall_score: float
    parser_warnings: list[str]
    limitations: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "metrics": self.metrics,
            "metric_notes": self.metric_notes,
            "candidate_results": self.candidate_results,
            "category_results": self.category_results,
            "overall_score": self.overall_score,
            "parser_warnings": self.parser_warnings,
            "limitations": self.limitations,
        }


def evaluate_benchmark(
    fixture: dict[str, Any], artifact: dict[str, Any], *, schema_valid: bool = True,
    provider_verification_valid: bool = True, fallback_used: bool = False,
    config: dict[str, Any] | None = None,
) -> EvaluationResult:
    config = config or load_scoring_config()
    candidates = _returned_candidates(artifact)
    returned_by_id = {candidate_identity(row): (rank, row) for rank, row in enumerate(candidates, 1) if candidate_identity(row)}
    categories = {row["category_name"]: row for row in fixture["categories"]}
    question = _key(fixture["benchmark"]["research_question"])
    expected_by_id: dict[str, dict[str, Any]] = {}
    candidate_results: list[dict[str, Any]] = []
    for security in fixture["securities"]:
        expected = dict(security)
        expected["_category_status"] = categories[security["category_name"]]["expected_status"]
        expectation = security["expectation"]
        expected["_reference_permitted"] = (
            expectation == "fund_reference" and any(term in question for term in ("reference vehicle", "fund", "etf"))
        ) or (
            expectation == "private_reference" and "private reference" in question
        ) or (
            expectation == "international_reference" and not any(term in question for term in ("us only", "u s only", "traditional u s banking"))
        )
        identity = _expected_identity(security)
        expected_by_id[identity] = expected
        match = returned_by_id.get(identity)
        returned = match is not None
        rank, candidate = match if match else (None, {})
        returned_category = candidate.get("category") or candidate.get("subdomain")
        violation = _listing_violation(candidate, expected) if returned else None
        candidate_results.append({
            "ticker": security.get("ticker"), "company_name": security.get("company_name"),
            "returned": returned, "returned_rank": rank,
            "expected_classification": security["expectation"],
            "expected_category": security["category_name"], "returned_category": returned_category,
            "category_match": returned and _key(returned_category) == _key(security["category_name"]),
            "rationale_present": bool(candidate.get("role_summary") and candidate.get("inclusion_rationale")),
            "evidence_present": _evidence_present(candidate),
            "listing_valid": returned and violation is None,
            "public_status_valid": returned and violation != "non_public_investable_candidate",
            "validation_status": candidate.get("entity_validation_status") if returned else "not_returned",
            "verified_public": bool(returned and security.get("public_status") == "public" and candidate.get("entity_validation_status") == "valid" and violation is None),
            "comparison_outcome": "expected_returned" if returned else "expected_missing",
            "reviewer_status": None, "reviewer_notes": None,
            "listing_violation": violation,
        })
    for rank, candidate in enumerate(candidates, 1):
        identity = candidate_identity(candidate)
        if identity in expected_by_id:
            continue
        violation = _listing_violation(candidate, None)
        candidate_results.append({
            "ticker": _ticker(candidate) or None, "company_name": candidate.get("company_name"),
            "returned": True, "returned_rank": rank, "expected_classification": None,
            "expected_category": None,
            "returned_category": candidate.get("category") or candidate.get("subdomain"),
            "category_match": False,
            "rationale_present": bool(candidate.get("role_summary") and candidate.get("inclusion_rationale")),
            "evidence_present": _evidence_present(candidate), "listing_valid": violation is None,
            "public_status_valid": violation is None,
            "validation_status": candidate.get("entity_validation_status") or "unverified",
            "verified_public": False,
            "comparison_outcome": "unexpected_candidate", "reviewer_status": "needs_verification",
            "reviewer_notes": None, "listing_violation": violation,
        })

    expected_returnable = [row for row in fixture["securities"] if row["expectation"] in config["candidate_weights"]]
    must = [row for row in expected_returnable if row["expectation"] == "must_include"]
    returned_ids = set(returned_by_id)
    must_recall = sum(_expected_identity(row) in returned_ids for row in must) / len(must) if must else 1.0
    weighted_denominator = sum(config["candidate_weights"][row["expectation"]] for row in expected_returnable)
    weighted_numerator = sum(config["candidate_weights"][row["expectation"]] for row in expected_returnable if _expected_identity(row) in returned_ids)
    weighted_recall = weighted_numerator / weighted_denominator if weighted_denominator else 1.0

    excluded_returned = sum(
        _expected_identity(row) in returned_ids for row in fixture["securities"] if row["expectation"] == "must_exclude"
    )
    must_exclude = max(0.0, 1.0 - excluded_returned * config["penalties"]["must_exclude_per_violation"])

    returned_category_names = _category_names(artifact, candidates)
    category_results: list[dict[str, Any]] = []
    coverage_num = coverage_den = 0.0
    excluded_categories_returned = 0
    for category in fixture["categories"]:
        status = category["expected_status"]
        returned = _key(category["category_name"]) in returned_category_names
        weight = float(config["category_weights"].get(status, 0.0))
        credit = weight if returned and status != "excluded" else 0.0
        if status != "excluded":
            coverage_num += credit
            coverage_den += weight
        elif returned:
            excluded_categories_returned += 1
        category_results.append({
            "category_name": category["category_name"], "expected_status": status,
            "importance": category["importance"], "returned": returned,
            "coverage_credit": credit, "notes": category.get("notes"),
        })
    category_coverage = max(0.0, (coverage_num / coverage_den if coverage_den else 1.0) - excluded_categories_returned * config["penalties"]["excluded_category_per_violation"])

    listing_violations = sum(bool(row.get("listing_violation")) for row in candidate_results if row["returned"])
    listing_compliance = max(0.0, 1.0 - listing_violations * config["penalties"]["listing_constraint_per_violation"])
    valid_count = sum(bool(row.get("verified_public")) for row in candidate_results if row["returned"])
    candidate_validity = valid_count / len(candidates) if candidates else 0.0
    rationale = sum(bool(row["rationale_present"]) for row in candidate_results if row["returned"]) / len(candidates) if candidates else 0.0
    evidence_supported = _artifact_supports_evidence(candidates)
    evidence = sum(bool(row["evidence_present"]) for row in candidate_results if row["returned"]) / len(candidates) if candidates else 0.0

    ranking_den = sum(config["candidate_weights"][row["expectation"]] for row in expected_returnable if row["expectation"] in {"must_include", "should_include"})
    ranking_num = 0.0
    for row in expected_returnable:
        if row["expectation"] not in {"must_include", "should_include"}:
            continue
        match = returned_by_id.get(_expected_identity(row))
        if match:
            ranking_num += config["candidate_weights"][row["expectation"]] / math.log2(match[0] + 1)
    ranking = ranking_num / ranking_den if ranking_den else 1.0
    integrity = float(schema_valid and provider_verification_valid and not fallback_used)
    metrics = {
        "must_include_recall": must_recall,
        "weighted_candidate_recall": weighted_recall,
        "must_exclude_compliance": must_exclude,
        "category_coverage": category_coverage,
        "listing_constraint_compliance": listing_compliance,
        "candidate_validity": candidate_validity,
        "rationale_completeness": rationale,
        "evidence_completeness": evidence,
        "ranking_quality": ranking,
        "schema_provider_integrity": integrity,
    }
    overall = sum(metrics[name] * float(weight) for name, weight in config["overall_weights"].items())
    notes = {
        "must_include_recall": f"{sum(_expected_identity(row) in returned_ids for row in must)}/{len(must)} must-include securities returned.",
        "weighted_candidate_recall": f"{weighted_numerator:g}/{weighted_denominator:g} weighted expected credit.",
        "must_exclude_compliance": f"{excluded_returned} explicit must-exclude violations.",
        "category_coverage": f"Weighted exact category matches; {excluded_categories_returned} excluded categories returned.",
        "listing_constraint_compliance": f"{listing_violations} deterministically observable listing/entity violations.",
        "candidate_validity": f"{valid_count}/{len(candidates)} candidates matched reviewed public-security references and passed current RCE entity validation; novel candidates remain unverified.",
        "rationale_completeness": "Requires both role_summary and inclusion_rationale.",
        "evidence_completeness": "Structured evidence fields detected." if evidence_supported else "Current RCE candidate artifact does not support structured evidence fields; reported as a limitation and excluded from overall score.",
        "ranking_quality": "Discounted rank credit (1/log2(rank+1)) for must-include and should-include securities.",
        "schema_provider_integrity": "Schema validity, provider verification, and fallback usage remain separately recorded.",
    }
    limitations = [] if evidence_supported else ["Structured candidate evidence is not supported by the current RCE artifact schema; evidence completeness is informational only."]
    warnings = [str(item) for item in artifact.get("warnings", [])] if isinstance(artifact.get("warnings"), list) else []
    return EvaluationResult(metrics, notes, candidate_results, category_results, round(overall, 6), warnings, limitations)


def estimate_cost(model: str, usage: dict[str, int], config: dict[str, Any] | None = None) -> float | None:
    config = config or load_scoring_config()
    rates = config.get("cost_per_million_tokens_usd", {}).get(model)
    if not rates:
        return None
    cached = max(0, int(usage.get("cached_input", 0)))
    total_input = max(0, int(usage.get("input", 0)))
    reasoning = max(0, int(usage.get("reasoning", 0)))
    total_output = max(0, int(usage.get("output", 0)))
    billable = {
        "input": max(0, total_input - cached),
        "cached_input": cached,
        "output": max(0, total_output - reasoning),
        "reasoning": reasoning,
    }
    cost = sum(float(billable[name]) * float(rate) / 1_000_000 for name, rate in rates.items())
    return round(cost, 8)
