"""Aggregations for validating one Opportunity Discovery quality-score run."""
from math import isfinite
from statistics import mean, median
from typing import Any

from src.contract_quality import ALL_PASSED_YES, QUALITY_CHECKS, near_miss_contracts
from src.opportunity_ranking import PASSING, TRUE_NEAR_MISS, quality_score_sort_value
from src.rule_evaluation import FAIL


RULES = {
    "Delta": "Delta Fit",
    "Spread": "Spread Pass",
    "Open Interest": "Open Interest Pass",
    "Volume": "Volume Pass",
}

CONTRIBUTION_RULES = {
    "Delta": "Delta Fit",
    "Spread": "Spread",
    "Open Interest": "Open Interest",
    "Volume": "Volume",
}

TOP_OPPORTUNITY_FIELDS = {
    "Average Quality Score": ("Quality Score",),
    "Average DTE": ("DTE",),
    "Average Strike Distance %": ("Strike Distance %", "Strike Distance (%)"),
    "Average Delta": ("Delta",),
    "Average Spread %": ("Spread %",),
    "Average Open Interest": ("Open Interest",),
    "Average Volume": ("Volume",),
}


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if isfinite(number) else None


def _numbers(rows: list[dict[str, Any]], *fields: str) -> list[float]:
    values = []
    for row in rows:
        for field in fields:
            value = _number(row.get(field))
            if value is not None:
                values.append(value)
                break
    return values


def _average(rows: list[dict[str, Any]], *fields: str) -> float | None:
    values = _numbers(rows, *fields)
    return mean(values) if values else None


def discovery_diagnostic_summary(rows: list[dict[str, Any]]) -> dict[str, float | int | None]:
    """Return headline scoring diagnostics for evaluated contracts from one run."""
    scores = _numbers(rows, "Quality Score")
    passing_count = sum(row.get("All Passed") == ALL_PASSED_YES for row in rows)
    true_near_miss_count = len(near_miss_contracts(rows))
    return {
        "Contracts Evaluated": len(rows),
        "Passing Contracts Count": passing_count,
        "True Near Miss Count": true_near_miss_count,
        "Rejected Count": max(len(rows) - passing_count - true_near_miss_count, 0),
        "Average Quality Score": mean(scores) if scores else None,
        "Median Quality Score": median(scores) if scores else None,
        "Highest Quality Score": max(scores) if scores else None,
        "Lowest Quality Score": min(scores) if scores else None,
    }


def quality_score_distribution(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Bucket quality scores into 10-point bands for Streamlit charting."""
    bucket_counts = {start: 0 for start in range(0, 100, 10)}
    for score in _numbers(rows, "Quality Score"):
        bucket_start = 90 if score >= 100 else max(min(int(score // 10) * 10, 90), 0)
        bucket_counts[bucket_start] += 1
    return [
        {"Score Bucket": f"{start}-{start + 10}", "Contracts": count}
        for start, count in bucket_counts.items()
    ]


def status_distribution(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Count passing, true near-miss, and rejected contracts from one run."""
    summary = discovery_diagnostic_summary(rows)
    return [
        {"Status": "Passing", "Contracts": summary["Passing Contracts Count"]},
        {"Status": "True Near Miss", "Contracts": summary["True Near Miss Count"]},
        {"Status": "Rejected", "Contracts": summary["Rejected Count"]},
    ]


def rule_failure_distribution(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Count explicit failures by current quality rule."""
    return [
        {
            "Rule": label,
            "Failures": sum(row.get(check) == FAIL for row in rows),
        }
        for label, check in RULES.items()
    ]


def average_rule_contribution(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return average score points earned by rule across evaluated contracts."""
    totals = {label: 0.0 for label in CONTRIBUTION_RULES}
    if not rows:
        return [{"Rule": label, "Average Points": 0.0} for label in CONTRIBUTION_RULES]

    for row in rows:
        breakdown = row.get("Quality Score Breakdown")
        breakdown = breakdown if isinstance(breakdown, list) else []
        points_by_rule = {
            item.get("Rule"): _number(item.get("Points")) or 0.0
            for item in breakdown
            if isinstance(item, dict)
        }
        for label, rule_name in CONTRIBUTION_RULES.items():
            totals[label] += points_by_rule.get(rule_name, 0.0)

    return [
        {"Rule": label, "Average Points": total / len(rows)}
        for label, total in totals.items()
    ]


def top_opportunity_summary(
    opportunity_rows: list[dict[str, Any]], limit: int = 10
) -> dict[str, float | None]:
    """Average metrics for the top ranked passing or near-miss opportunities."""
    candidates = [
        row
        for row in opportunity_rows
        if row.get("Status") in {PASSING, TRUE_NEAR_MISS}
        and _number(row.get("Quality Score")) is not None
    ]
    top_rows = sorted(candidates, key=quality_score_sort_value, reverse=True)[:limit]
    return {
        label: _average(top_rows, *fields)
        for label, fields in TOP_OPPORTUNITY_FIELDS.items()
    }
