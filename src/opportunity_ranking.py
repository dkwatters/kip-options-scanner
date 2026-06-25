"""Rank the best currently evaluated option opportunity per watchlist ticker."""
from typing import Any

from src.contract_quality import (
    DIAGNOSTIC_LABELS,
    QUALITY_CHECKS,
    near_miss_contracts,
    passing_contracts,
)
from src.rule_evaluation import FAIL, PASS


PASSING = "Passing"
TRUE_NEAR_MISS = "True Near Miss"


def quality_score_sort_value(row: dict[str, Any]) -> float:
    """Return a stable numeric sort value for already-scored contracts."""
    try:
        return float(row.get("Quality Score"))
    except (TypeError, ValueError):
        return float("-inf")


def best_quality_contract(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Return the highest-quality contract from an evaluated row collection."""
    return max(rows, key=quality_score_sort_value) if rows else None


def selected_watchlist_contract(rows: list[dict[str, Any]]) -> tuple[dict[str, Any], str] | tuple[None, None]:
    """Select the best passing contract, otherwise the best true near miss."""
    passing_candidate = best_quality_contract(passing_contracts(rows))
    if passing_candidate is not None:
        return passing_candidate, PASSING

    near_miss_candidate = best_quality_contract(near_miss_contracts(rows))
    if near_miss_candidate is not None:
        return near_miss_candidate, TRUE_NEAR_MISS

    return None, None


def primary_contract_weakness(row: dict[str, Any]) -> str:
    """Return the failed rule label most relevant to the selected contract."""
    failed = [
        DIAGNOSTIC_LABELS[check]
        for check in QUALITY_CHECKS
        if row.get(check) == FAIL
    ]
    return ", ".join(failed) if failed else "None"


def primary_contract_strength(row: dict[str, Any]) -> str:
    """Return the passed rule label with the strongest score contribution."""
    breakdown = row.get("Quality Score Breakdown")
    if not isinstance(breakdown, list):
        return "None"
    passed = [
        item
        for item in breakdown
        if isinstance(item, dict) and item.get("Pass/Fail") == PASS
    ]
    if not passed:
        return "None"
    best_points = max(item.get("Points", 0) for item in passed)
    labels = [item.get("Rule", "Unknown") for item in passed if item.get("Points", 0) == best_points]
    return ", ".join(labels)


def opportunity_table_rows(
    ticker_rows: dict[str, list[dict[str, Any]]]
) -> list[dict[str, Any]]:
    """Build ranked opportunity rows from evaluated contracts keyed by ticker."""
    opportunities = []
    for ticker, rows in ticker_rows.items():
        selected_contract, status = selected_watchlist_contract(rows)
        if selected_contract is None:
            continue

        opportunities.append(
            {
                **selected_contract,
                "Ticker": ticker,
                "Status": status,
                "Primary Weakness": primary_contract_weakness(selected_contract),
                "Primary Strength": primary_contract_strength(selected_contract),
            }
        )

    ranked = sorted(opportunities, key=quality_score_sort_value, reverse=True)
    for index, row in enumerate(ranked, start=1):
        row["Rank"] = index
    return ranked
