"""Aggregations for validating one Opportunity Discovery quality-score run."""
from math import isfinite
from statistics import mean, median
from typing import Any

from src.contract_quality import (
    ALL_PASSED_YES,
    QUALITY_CHECKS,
    near_miss_contracts,
    passing_contracts,
)
from src.contract_scoring import QUALITY_WEIGHTS
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

WEIGHT_LABELS = {
    "Delta Fit": "Delta",
}

FINGERPRINT_FIELDS = {
    "Average Quality Score": ("Quality Score",),
    "Average DTE": ("DTE",),
    "Average Delta": ("Delta",),
    "Average Spread %": ("Spread %",),
    "Average Open Interest": ("Open Interest",),
    "Average Volume": ("Volume",),
    "Average Strike Distance %": ("Strike Distance %", "Strike Distance (%)"),
}

SCORE_BUCKETS = (
    (0, 50),
    (50, 60),
    (60, 70),
    (70, 80),
    (80, 85),
    (85, 90),
    (90, 95),
    (95, 100),
)

ALL_CONTRACTS_POPULATION = "All Contracts"
REJECTED_CONTRACTS_POPULATION = "Rejected Contracts"
TRUE_NEAR_MISS_CONTRACTS_POPULATION = "True Near Miss Contracts"
PASSING_CONTRACTS_POPULATION = "Passing Contracts"

DISTRIBUTION_POPULATIONS = (
    ALL_CONTRACTS_POPULATION,
    REJECTED_CONTRACTS_POPULATION,
    TRUE_NEAR_MISS_CONTRACTS_POPULATION,
    PASSING_CONTRACTS_POPULATION,
)

DEFAULT_DISTRIBUTION_POPULATION = REJECTED_CONTRACTS_POPULATION
REJECTED_VS_PASSING_COMPARISON = "Rejected vs Passing"
REJECTED_VS_TRUE_NEAR_MISS_COMPARISON = "Rejected vs True Near Miss"
TRUE_NEAR_MISS_VS_PASSING_COMPARISON = "True Near Miss vs Passing"

DISTRIBUTION_COMPARISONS = {
    REJECTED_VS_PASSING_COMPARISON: (
        REJECTED_CONTRACTS_POPULATION,
        PASSING_CONTRACTS_POPULATION,
    ),
    REJECTED_VS_TRUE_NEAR_MISS_COMPARISON: (
        REJECTED_CONTRACTS_POPULATION,
        TRUE_NEAR_MISS_CONTRACTS_POPULATION,
    ),
    TRUE_NEAR_MISS_VS_PASSING_COMPARISON: (
        TRUE_NEAR_MISS_CONTRACTS_POPULATION,
        PASSING_CONTRACTS_POPULATION,
    ),
}

DEFAULT_DISTRIBUTION_COMPARISON = REJECTED_VS_PASSING_COMPARISON

UNAVAILABLE_BUCKET = "Unavailable"
OUT_OF_RANGE_BUCKET = "Out of Range"
PASS_ZONE = "Pass Zone"
BORDERLINE_ZONE = "Borderline"
FAIL_ZONE = "Fail Zone"

DELTA_BUCKETS = (
    ("< 0.20", None, 0.20, False, False),
    ("0.20-0.30", 0.20, 0.30, True, False),
    ("0.30-0.40", 0.30, 0.40, True, False),
    ("0.40-0.45", 0.40, 0.45, True, False),
    ("0.45-0.50", 0.45, 0.50, True, False),
    ("0.50-0.60", 0.50, 0.60, True, False),
    ("0.60-0.70", 0.60, 0.70, True, False),
    ("> 0.70", 0.70, None, False, False),
)

SPREAD_PERCENT_BUCKETS = (
    ("0-1%", 0.00, 0.01, True, False),
    ("1-2%", 0.01, 0.02, True, False),
    ("2-3%", 0.02, 0.03, True, False),
    ("3-4%", 0.03, 0.04, True, False),
    ("4-5%", 0.04, 0.05, True, False),
    ("5-7.5%", 0.05, 0.075, True, False),
    ("7.5-10%", 0.075, 0.10, True, False),
    ("> 10%", 0.10, None, False, False),
)

VOLUME_BUCKETS = (
    ("0", 0, 0, True, True),
    ("1-100", 1, 100, True, True),
    ("101-250", 101, 250, True, True),
    ("251-500", 251, 500, True, True),
    ("501-1,000", 501, 1_000, True, True),
    ("1,001-2,500", 1_001, 2_500, True, True),
    ("> 2,500", 2_500, None, False, False),
)

OPEN_INTEREST_BUCKETS = (
    ("0", 0, 0, True, True),
    ("1-250", 1, 250, True, True),
    ("251-500", 251, 500, True, True),
    ("501-1,000", 501, 1_000, True, True),
    ("1,001-2,500", 1_001, 2_500, True, True),
    ("2,501-5,000", 2_501, 5_000, True, True),
    ("> 5,000", 5_000, None, False, False),
)

DISTRIBUTION_BUCKETS = {
    "Delta Distribution": DELTA_BUCKETS,
    "Spread % Distribution": SPREAD_PERCENT_BUCKETS,
    "Volume Distribution": VOLUME_BUCKETS,
    "Open Interest Distribution": OPEN_INTEREST_BUCKETS,
}

DISTRIBUTION_FIELDS = {
    "Delta Distribution": "Delta",
    "Spread % Distribution": "Spread %",
    "Volume Distribution": "Volume",
    "Open Interest Distribution": "Open Interest",
}

DISTRIBUTION_BUCKET_ZONES = {
    "Delta Distribution": {
        "< 0.20": FAIL_ZONE,
        "0.20-0.30": FAIL_ZONE,
        "0.30-0.40": FAIL_ZONE,
        "0.40-0.45": FAIL_ZONE,
        "0.45-0.50": BORDERLINE_ZONE,
        "0.50-0.60": PASS_ZONE,
        "0.60-0.70": PASS_ZONE,
        "> 0.70": BORDERLINE_ZONE,
    },
    "Spread % Distribution": {
        "0-1%": PASS_ZONE,
        "1-2%": PASS_ZONE,
        "2-3%": PASS_ZONE,
        "3-4%": PASS_ZONE,
        "4-5%": PASS_ZONE,
        "5-7.5%": BORDERLINE_ZONE,
        "7.5-10%": FAIL_ZONE,
        "> 10%": FAIL_ZONE,
    },
    "Volume Distribution": {
        "0": FAIL_ZONE,
        "1-100": FAIL_ZONE,
        "101-250": FAIL_ZONE,
        "251-500": BORDERLINE_ZONE,
        "501-1,000": PASS_ZONE,
        "1,001-2,500": PASS_ZONE,
        "> 2,500": PASS_ZONE,
    },
    "Open Interest Distribution": {
        "0": FAIL_ZONE,
        "1-250": FAIL_ZONE,
        "251-500": FAIL_ZONE,
        "501-1,000": BORDERLINE_ZONE,
        "1,001-2,500": PASS_ZONE,
        "2,501-5,000": PASS_ZONE,
        "> 5,000": PASS_ZONE,
    },
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


def _explicit_failure_count(row: dict[str, Any]) -> int:
    return sum(row.get(check) == FAIL for check in QUALITY_CHECKS)


def _is_rejected_contract(row: dict[str, Any]) -> bool:
    return row.get("All Passed") != ALL_PASSED_YES and _explicit_failure_count(row) != 1


def _observation_number(value: float) -> str:
    """Render observation values compactly without hiding non-integer averages."""
    return f"{value:.0f}" if value.is_integer() else f"{value:.1f}"


def _in_bucket(
    value: float,
    lower: float | None,
    upper: float | None,
    include_lower: bool,
    include_upper: bool,
) -> bool:
    if lower is not None:
        if value < lower or (value == lower and not include_lower):
            return False
    if upper is not None:
        if value > upper or (value == upper and not include_upper):
            return False
    return True


def _bucket_label(
    value: float | None,
    buckets: tuple[tuple[str, float | None, float | None, bool, bool], ...],
) -> str:
    if value is None:
        return UNAVAILABLE_BUCKET
    for label, lower, upper, include_lower, include_upper in buckets:
        if _in_bucket(value, lower, upper, include_lower, include_upper):
            return label
    return OUT_OF_RANGE_BUCKET


def _distribution_rows(
    distribution_label: str,
    rows: list[dict[str, Any]],
    field: str,
    buckets: tuple[tuple[str, float | None, float | None, bool, bool], ...],
    use_absolute_value: bool = False,
) -> list[dict[str, Any]]:
    total = len(rows)
    bucket_labels = [bucket[0] for bucket in buckets] + [UNAVAILABLE_BUCKET, OUT_OF_RANGE_BUCKET]
    counts = {label: 0 for label in bucket_labels}

    for row in rows:
        value = _number(row.get(field))
        if value is not None and use_absolute_value:
            value = abs(value)
        counts[_bucket_label(value, buckets)] += 1

    return [
        {
            "Bucket": bucket_label,
            "Zone": DISTRIBUTION_BUCKET_ZONES.get(distribution_label, {}).get(
                bucket_label, FAIL_ZONE
            ),
            "Count": count,
            "Percentage": count / total if total else None,
        }
        for bucket_label, count in counts.items()
        if count or bucket_label not in {UNAVAILABLE_BUCKET, OUT_OF_RANGE_BUCKET}
    ]


def _distribution_bucket_order(distribution_label: str) -> list[str]:
    return [
        bucket[0] for bucket in DISTRIBUTION_BUCKETS[distribution_label]
    ] + [UNAVAILABLE_BUCKET, OUT_OF_RANGE_BUCKET]


def _population_column_label(population: str) -> str:
    return population.removesuffix(" Contracts")


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


def distribution_population(
    rows: list[dict[str, Any]], population: str
) -> list[dict[str, Any]]:
    """Return evaluated contracts for the selected diagnostic population."""
    if population == ALL_CONTRACTS_POPULATION:
        return rows
    if population == PASSING_CONTRACTS_POPULATION:
        return passing_contracts(rows)
    if population == TRUE_NEAR_MISS_CONTRACTS_POPULATION:
        return near_miss_contracts(rows)
    if population == REJECTED_CONTRACTS_POPULATION:
        return [row for row in rows if _is_rejected_contract(row)]
    return []


def distribution_population_summary(
    rows: list[dict[str, Any]]
) -> dict[str, float | int | None]:
    """Return summary metrics for a selected diagnostic population."""
    return {
        "Population Count": len(rows),
        "Average Quality Score": _average(rows, "Quality Score"),
        "Average Delta": _average(rows, "Delta"),
        "Average Spread %": _average(rows, "Spread %"),
        "Average Volume": _average(rows, "Volume"),
        "Average Open Interest": _average(rows, "Open Interest"),
    }


def quality_variable_distributions(
    rows: list[dict[str, Any]]
) -> dict[str, list[dict[str, Any]]]:
    """Bucket core quality variables for the selected diagnostic population."""
    return {
        label: _distribution_rows(
            label,
            rows,
            DISTRIBUTION_FIELDS[label],
            buckets,
            use_absolute_value=label == "Delta Distribution",
        )
        for label, buckets in DISTRIBUTION_BUCKETS.items()
    }


def comparison_quality_variable_distributions(
    rows: list[dict[str, Any]],
    population_a: str,
    population_b: str,
) -> dict[str, list[dict[str, Any]]]:
    """Bucket core quality variables for two populations using identical buckets."""
    rows_a = distribution_population(rows, population_a)
    rows_b = distribution_population(rows, population_b)
    distributions_a = quality_variable_distributions(rows_a)
    distributions_b = quality_variable_distributions(rows_b)
    label_a = _population_column_label(population_a)
    label_b = _population_column_label(population_b)

    comparisons = {}
    for distribution_label in DISTRIBUTION_BUCKETS:
        rows_by_bucket_a = {
            row["Bucket"]: row for row in distributions_a[distribution_label]
        }
        rows_by_bucket_b = {
            row["Bucket"]: row for row in distributions_b[distribution_label]
        }
        comparison_rows = []
        for bucket in _distribution_bucket_order(distribution_label):
            row_a = rows_by_bucket_a.get(bucket)
            row_b = rows_by_bucket_b.get(bucket)
            if bucket in {UNAVAILABLE_BUCKET, OUT_OF_RANGE_BUCKET} and not row_a and not row_b:
                continue
            comparison_rows.append(
                {
                    "Bucket": bucket,
                    "Zone": DISTRIBUTION_BUCKET_ZONES.get(distribution_label, {}).get(
                        bucket, FAIL_ZONE
                    ),
                    f"{label_a} Count": row_a["Count"] if row_a else 0,
                    f"{label_a} %": row_a["Percentage"] if row_a else None,
                    f"{label_b} Count": row_b["Count"] if row_b else 0,
                    f"{label_b} %": row_b["Percentage"] if row_b else None,
                }
            )
        comparisons[distribution_label] = comparison_rows
    return comparisons


def quality_score_distribution(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Bucket quality scores into diagnostic bands with detail above 80."""
    bucket_counts = {f"{start}-{end}": 0 for start, end in SCORE_BUCKETS}
    for score in _numbers(rows, "Quality Score"):
        for start, end in SCORE_BUCKETS:
            if score < end or end == 100:
                bucket_counts[f"{start}-{end}"] += 1
                break
    return [
        {"Score Bucket": bucket, "Contracts": count}
        for bucket, count in bucket_counts.items()
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
    """Count explicit failures by current quality rule and evaluated total."""
    evaluated_count = len(rows)
    return [
        {
            "Rule": label,
            "Failure Count": failure_count,
            "Failure Percentage": failure_count / evaluated_count
            if evaluated_count
            else None,
            "Failure Summary": f"{failure_count:,} failures "
            f"({failure_count / evaluated_count:.0%})"
            if evaluated_count
            else f"{failure_count:,} failures (-)",
        }
        for label, check in RULES.items()
        for failure_count in [sum(row.get(check) == FAIL for row in rows)]
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


def contract_fingerprint(rows: list[dict[str, Any]]) -> dict[str, float | None]:
    """Average current quality fields for a supplied contract collection."""
    return {
        label: _average(rows, *fields)
        for label, fields in FINGERPRINT_FIELDS.items()
    }


def passing_contract_fingerprint(rows: list[dict[str, Any]]) -> dict[str, float | None]:
    """Average quality fields across contracts passing all current rules."""
    passing_rows = [row for row in rows if row.get("All Passed") == ALL_PASSED_YES]
    return contract_fingerprint(passing_rows)


def top_opportunity_fingerprint(
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
    return contract_fingerprint(top_rows)


def dashboard_metadata(
    rows: list[dict[str, Any]],
    watchlist: list[str],
    option_type: str,
    min_dte: int,
    max_dte: int,
    scan_timestamp: str | None,
    weights: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Return run context needed to compare one dashboard screenshot to another."""
    option_types = [
        str(row.get("Option Type", "")).lower()
        for row in rows
        if row.get("Option Type") not in (None, "")
    ]
    calls = sum(option_type == "call" for option_type in option_types)
    puts = sum(option_type == "put" for option_type in option_types)
    quality_weights = weights or QUALITY_WEIGHTS
    return {
        "Scan Timestamp": scan_timestamp,
        "Watchlist Size": len(watchlist),
        "Contracts Evaluated": len(rows),
        "Calls / Puts": f"{calls:,} / {puts:,}",
        "DTE Range": f"{min_dte}-{max_dte}",
        "Current Quality Score Weights": ", ".join(
            f"{WEIGHT_LABELS.get(rule, rule)} {weight}"
            for rule, weight in quality_weights.items()
        ),
        "Discovery Option Type": option_type,
    }


def dashboard_observations(
    evaluated_rows: list[dict[str, Any]],
    opportunity_rows: list[dict[str, Any]],
) -> list[str]:
    """Return measured facts about the current dashboard data only."""
    observations = []
    summary = discovery_diagnostic_summary(evaluated_rows)
    evaluated_count = summary["Contracts Evaluated"]
    if evaluated_count:
        rejected_percentage = summary["Rejected Count"] / evaluated_count
        observations.append(
            f"{rejected_percentage:.0%} of evaluated contracts were rejected."
        )

    failures = rule_failure_distribution(evaluated_rows)
    highest_failure_count = max(
        (row["Failure Count"] for row in failures),
        default=0,
    )
    if highest_failure_count:
        most_common_rules = [
            row["Rule"] for row in failures if row["Failure Count"] == highest_failure_count
        ]
        plural = len(most_common_rules) > 1
        verb = "were" if plural else "was"
        noun = "rules" if plural else "rule"
        observations.append(
            f"{', '.join(most_common_rules)} {verb} the most common failing {noun}."
        )

    passing_fingerprint = passing_contract_fingerprint(evaluated_rows)
    average_passing_score = passing_fingerprint["Average Quality Score"]
    if average_passing_score is not None:
        observations.append(
            f"Average Passing Quality Score = {_observation_number(average_passing_score)}."
        )

    ranked_opportunities = [
        row
        for row in opportunity_rows
        if row.get("Status") in {PASSING, TRUE_NEAR_MISS}
        and _number(row.get("Quality Score")) is not None
    ]
    if ranked_opportunities:
        highest_ranked = sorted(
            ranked_opportunities,
            key=quality_score_sort_value,
            reverse=True,
        )[0]
        observations.append(
            f"Highest-ranked opportunity scored {float(highest_ranked['Quality Score']):.0f}."
        )

    return observations


def top_opportunity_summary(
    opportunity_rows: list[dict[str, Any]], limit: int = 10
) -> dict[str, float | None]:
    """Backward-compatible wrapper for the top opportunity fingerprint."""
    return top_opportunity_fingerprint(opportunity_rows, limit)
