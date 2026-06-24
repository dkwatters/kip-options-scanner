"""Reusable option-contract quality calculations.

This module is intentionally independent of market-data providers and UI code.
"""
from datetime import date, datetime
from typing import Any

from src.rule_evaluation import (
    FAIL,
    NOT_AVAILABLE,
    PASS,
    RuleEvaluation,
    evaluate_maximum,
    evaluate_minimum,
    evaluate_range,
)


ALL_PASSED_YES = "Yes"
ALL_PASSED_NO = "No"

QUALITY_CHECKS = (
    "Delta Fit",
    "Open Interest Pass",
    "Volume Pass",
    "Spread Pass",
)

FAILED_TEST_ABBREVIATIONS = {
    "Delta Fit": "Δ",
    "Open Interest Pass": "OI",
    "Volume Pass": "Vol",
    "Spread Pass": "Spr",
}

DIAGNOSTIC_LABELS = {
    "Delta Fit": "Delta",
    "Spread Pass": "Spread",
    "Volume Pass": "Volume",
    "Open Interest Pass": "OI",
}

TEST_SPECIFIC_NEAR_MISS_OPTIONS = {
    "Delta": "Delta Fit",
    "Spread": "Spread Pass",
    "Open Interest": "Open Interest Pass",
    "Volume": "Volume Pass",
}

ANY_SINGLE_FAILED_TEST = "Any single failed test"
OPTION_TYPE_FILTERS = {
    "Calls": "call",
    "Puts": "put",
}

RULE_DETAIL_COLUMNS = {
    "Delta Fit": "Delta Rule Detail",
    "Spread Pass": "Spread Rule Detail",
    "Open Interest Pass": "OI Rule Detail",
    "Volume Pass": "Volume Rule Detail",
}

RULE_MARGIN_COLUMNS = {
    "Delta Fit": "Delta Margin",
    "Spread Pass": "Spread Margin",
    "Open Interest Pass": "OI Margin",
    "Volume Pass": "Volume Margin",
}

CALL_DELTA_RANGE = (0.50, 0.70)
PUT_DELTA_RANGE = (-0.70, -0.50)
MIN_OPEN_INTEREST = 1_000
MIN_VOLUME = 500
MAX_SPREAD_PERCENT = 0.05


def _number(value: Any) -> float | None:
    """Return a finite numeric value, or None when a field is unavailable."""
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if result == result and result not in (float("inf"), float("-inf")) else None


def _date(value: Any) -> date | None:
    """Parse a date or ISO-format date string returned by an option provider."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def calculate_mid_price(bid: Any, ask: Any) -> float | str:
    bid_value, ask_value = _number(bid), _number(ask)
    if bid_value is None or ask_value is None:
        return NOT_AVAILABLE
    return (bid_value + ask_value) / 2


def calculate_spread(bid: Any, ask: Any) -> float | str:
    bid_value, ask_value = _number(bid), _number(ask)
    if bid_value is None or ask_value is None:
        return NOT_AVAILABLE
    return ask_value - bid_value


def calculate_spread_percent(mid_price: Any, spread: Any) -> float | str:
    mid_value, spread_value = _number(mid_price), _number(spread)
    if mid_value is None or spread_value is None or mid_value <= 0:
        return NOT_AVAILABLE
    return spread_value / mid_value


def calculate_strike_distance_percent(strike: Any, underlying_price: Any) -> float | str:
    """Return a contract strike's absolute distance from the underlying price."""
    strike_value, underlying_value = _number(strike), _number(underlying_price)
    if strike_value is None or underlying_value is None or underlying_value <= 0:
        return NOT_AVAILABLE
    return abs(strike_value - underlying_value) / underlying_value


def calculate_dte(expiration: Any, today: date | None = None) -> int | str:
    expiration_date = _date(expiration)
    if expiration_date is None:
        return NOT_AVAILABLE
    return (expiration_date - (today or date.today())).days


def delta_fit(option_type: Any, delta: Any) -> str:
    return delta_rule(option_type, delta).result


def delta_rule(option_type: Any, delta: Any) -> RuleEvaluation:
    """Evaluate whether delta is in the target range for the option type."""
    if not isinstance(option_type, str):
        return RuleEvaluation("Delta Fit", NOT_AVAILABLE, NOT_AVAILABLE, NOT_AVAILABLE, NOT_AVAILABLE)
    if option_type.lower() == "call":
        return evaluate_range("Delta Fit", delta, *CALL_DELTA_RANGE)
    if option_type.lower() == "put":
        return evaluate_range("Delta Fit", delta, *PUT_DELTA_RANGE)
    return RuleEvaluation("Delta Fit", NOT_AVAILABLE, NOT_AVAILABLE, NOT_AVAILABLE, NOT_AVAILABLE)


def minimum_pass(value: Any, minimum: float) -> str:
    return evaluate_minimum("Minimum", value, minimum).result


def spread_pass(spread_percent: Any) -> str:
    return evaluate_maximum("Spread %", spread_percent, MAX_SPREAD_PERCENT).result


def all_quality_checks_pass(quality_fields: dict[str, Any]) -> str:
    """Return whether every current contract-quality check passed."""
    return (
        ALL_PASSED_YES
        if all(quality_fields.get(check) == PASS for check in QUALITY_CHECKS)
        else ALL_PASSED_NO
    )


def failed_tests(quality_fields: dict[str, Any]) -> str:
    """Return abbreviations for the current quality checks that explicitly failed."""
    failures = [
        FAILED_TEST_ABBREVIATIONS[check]
        for check in QUALITY_CHECKS
        if quality_fields.get(check) == FAIL
    ]
    return ", ".join(failures) if failures else "—"


def contract_quality(
    contract: dict[str, Any],
    expiration: Any = None,
    today: date | None = None,
    underlying_price: Any = None,
) -> dict[str, Any]:
    """Calculate display-ready quality fields for one raw option contract."""
    bid = contract.get("bid")
    ask = contract.get("ask")
    greeks = contract.get("greeks")
    greeks = greeks if isinstance(greeks, dict) else {}

    mid = calculate_mid_price(bid, ask)
    spread = calculate_spread(bid, ask)
    spread_percent = calculate_spread_percent(mid, spread)
    option_type = contract.get("option_type")
    delta = greeks.get("delta")
    expiration_value = expiration if expiration is not None else contract.get("expiration_date")

    evaluations = {
        "Delta Fit": delta_rule(option_type, delta),
        "Spread Pass": evaluate_maximum("Spread %", spread_percent, MAX_SPREAD_PERCENT),
        "Open Interest Pass": evaluate_minimum(
            "Open Interest", contract.get("open_interest"), MIN_OPEN_INTEREST
        ),
        "Volume Pass": evaluate_minimum("Volume", contract.get("volume"), MIN_VOLUME),
    }

    quality_fields = {
        "Mid Price": mid,
        "Spread": spread,
        "Spread %": spread_percent,
        "Strike Distance %": calculate_strike_distance_percent(
            contract.get("strike"), underlying_price
        ),
        "DTE": calculate_dte(expiration_value, today),
        **{column: evaluation.result for column, evaluation in evaluations.items()},
        "Delta Rule Detail": evaluations["Delta Fit"].detail(),
        "Spread Rule Detail": evaluations["Spread Pass"].detail(),
        "OI Rule Detail": evaluations["Open Interest Pass"].detail(),
        "Volume Rule Detail": evaluations["Volume Pass"].detail(),
        "Delta Margin": evaluations["Delta Fit"].margin,
        "Spread Margin": evaluations["Spread Pass"].margin,
        "OI Margin": evaluations["Open Interest Pass"].margin,
        "Volume Margin": evaluations["Volume Pass"].margin,
    }
    quality_fields["All Passed"] = all_quality_checks_pass(quality_fields)
    quality_fields["Failed Tests"] = failed_tests(quality_fields)
    return quality_fields


def passing_contracts(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return contracts that satisfy every explicit quality rule."""
    return [row for row in rows if row.get("All Passed") == ALL_PASSED_YES]


def filter_by_option_type(
    rows: list[dict[str, Any]], option_type: str
) -> list[dict[str, Any]]:
    """Return rows matching the requested diagnostic option-type filter."""
    requested_type = OPTION_TYPE_FILTERS[option_type]
    if requested_type is None:
        return rows
    return [
        row
        for row in rows
        if isinstance(row.get("Option Type"), str)
        and row["Option Type"].lower() == requested_type
    ]


def near_miss_contracts(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return contracts with exactly one explicit quality-test failure."""
    return [
        row
        for row in rows
        if sum(row.get(check) == FAIL for check in QUALITY_CHECKS) == 1
    ]


def test_specific_near_misses(
    rows: list[dict[str, Any]], selected_test: str
) -> list[dict[str, Any]]:
    """Return selected-test failures, closest to passing first.

    Rule margins are positive for passes and negative for failures. Sorting a
    failed test's margin descending therefore puts the smallest shortfall first.
    """
    check = TEST_SPECIFIC_NEAR_MISS_OPTIONS[selected_test]
    margin_column = RULE_MARGIN_COLUMNS[check]

    def margin(row: dict[str, Any]) -> float:
        value = _number(row.get(margin_column))
        return value if value is not None else float("-inf")

    return sorted(
        (row for row in rows if row.get(check) == FAIL),
        key=margin,
        reverse=True,
    )


def closest_test_near_miss(
    rows: list[dict[str, Any]], selected_test: str
) -> dict[str, Any] | None:
    """Return the closest true near miss whose only failure is one rule.

    The rule framework defines failed margins as negative values. Selecting the
    greatest available failed margin therefore selects the true near miss
    nearest to passing without changing the rule or introducing a score.
    """
    check = TEST_SPECIFIC_NEAR_MISS_OPTIONS[selected_test]
    margin_column = RULE_MARGIN_COLUMNS[check]
    candidates = [
        row
        for row in near_miss_contracts(rows)
        if row.get(check) == FAIL and _number(row.get(margin_column)) is not None
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda row: _number(row.get(margin_column)))


def closest_true_near_miss(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Return the true near miss with the greatest failed-rule margin.

    A true near miss has exactly one explicit failed check, so its failed rule
    margin is unambiguous. This uses the same margin ordering as the existing
    drilldowns: a value nearer zero is closer to passing.
    """
    candidates: list[tuple[dict[str, Any], float]] = []
    for row in near_miss_contracts(rows):
        failed_check = next(
            (check for check in QUALITY_CHECKS if row.get(check) == FAIL), None
        )
        margin = _number(row.get(RULE_MARGIN_COLUMNS[failed_check])) if failed_check else None
        if margin is not None:
            candidates.append((row, margin))
    return max(candidates, key=lambda candidate: candidate[1])[0] if candidates else None


def contract_quality_summary(rows: list[dict[str, Any]]) -> dict[str, int]:
    """Count validation outcomes for a collection of display-ready contract rows."""
    return {
        "Total Contracts": len(rows),
        "Delta Fit Pass Count": sum(row.get("Delta Fit") == PASS for row in rows),
        "Spread Pass Count": sum(row.get("Spread Pass") == PASS for row in rows),
        "Open Interest Pass Count": sum(row.get("Open Interest Pass") == PASS for row in rows),
        "Volume Pass Count": sum(row.get("Volume Pass") == PASS for row in rows),
        "All Quality Checks Pass Count": sum(
            row.get("All Passed") == ALL_PASSED_YES for row in rows
        ),
    }


def ticker_diagnostics(rows: list[dict[str, Any]]) -> dict[str, int | str]:
    """Aggregate contract-quality outcomes for one selected ticker chain.

    A primary weakness is the check with the most explicit failures. A primary
    strength is the check with the most explicit passes. Unavailable outcomes
    are excluded from both counts. Ties retain each tied check rather than
    inventing a ranking between them.
    """
    failure_counts = {
        check: sum(row.get(check) == FAIL for row in rows) for check in QUALITY_CHECKS
    }
    pass_counts = {
        check: sum(row.get(check) == PASS for row in rows) for check in QUALITY_CHECKS
    }

    def primary_label(counts: dict[str, int], empty_label: str) -> str:
        highest_count = max(counts.values(), default=0)
        if highest_count == 0:
            return empty_label
        primary_checks = [
            DIAGNOSTIC_LABELS[check]
            for check in QUALITY_CHECKS
            if counts[check] == highest_count
        ]
        label = ", ".join(primary_checks)
        return f"{label} (tie)" if len(primary_checks) > 1 else label

    return {
        "Contracts Evaluated": len(rows),
        "Contracts Passing All Tests": sum(
            row.get("All Passed") == ALL_PASSED_YES for row in rows
        ),
        "Delta Failure Count": failure_counts["Delta Fit"],
        "Spread Failure Count": failure_counts["Spread Pass"],
        "Volume Failure Count": failure_counts["Volume Pass"],
        "OI Failure Count": failure_counts["Open Interest Pass"],
        "Primary Weakness": primary_label(failure_counts, "None"),
        "Primary Strength": primary_label(pass_counts, "None"),
    }


def opportunity_analysis(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize contract-quality opportunities for one ticker chain.

    This is an aggregation of existing pass/fail results and rule margins only.
    It intentionally does not score, rank, or recommend contracts.
    """
    diagnostics = ticker_diagnostics(rows)
    return {
        "Contracts Evaluated": len(rows),
        "Passing Contracts Count": len(passing_contracts(rows)),
        "True Near Miss Count": len(near_miss_contracts(rows)),
        "Closest Near Miss": closest_true_near_miss(rows),
        "Closest Spread Near Miss": closest_test_near_miss(rows, "Spread"),
        "Closest Delta Near Miss": closest_test_near_miss(rows, "Delta"),
        "Closest Open Interest Near Miss": closest_test_near_miss(rows, "Open Interest"),
        "Closest Volume Near Miss": closest_test_near_miss(rows, "Volume"),
        "Primary Weakness": diagnostics["Primary Weakness"],
        "Primary Strength": diagnostics["Primary Strength"],
    }
