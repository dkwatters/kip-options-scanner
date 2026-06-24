"""Reusable option-contract quality calculations.

This module is intentionally independent of market-data providers and UI code.
"""
from datetime import date, datetime
from typing import Any


NOT_AVAILABLE = "N/A"
PASS = "Pass"
FAIL = "Fail"
ALL_PASSED_YES = "Yes"
ALL_PASSED_NO = "No"

QUALITY_CHECKS = (
    "Delta Fit",
    "Open Interest Pass",
    "Volume Pass",
    "Spread Pass",
)

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
    delta_value = _number(delta)
    if delta_value is None or not isinstance(option_type, str):
        return NOT_AVAILABLE
    if option_type.lower() == "call":
        return PASS if CALL_DELTA_RANGE[0] <= delta_value <= CALL_DELTA_RANGE[1] else FAIL
    if option_type.lower() == "put":
        return PASS if PUT_DELTA_RANGE[0] <= delta_value <= PUT_DELTA_RANGE[1] else FAIL
    return NOT_AVAILABLE


def minimum_pass(value: Any, minimum: float) -> str:
    numeric_value = _number(value)
    if numeric_value is None:
        return NOT_AVAILABLE
    return PASS if numeric_value >= minimum else FAIL


def spread_pass(spread_percent: Any) -> str:
    value = _number(spread_percent)
    if value is None:
        return NOT_AVAILABLE
    return PASS if value <= MAX_SPREAD_PERCENT else FAIL


def all_quality_checks_pass(quality_fields: dict[str, Any]) -> str:
    """Return whether every current contract-quality check passed."""
    return (
        ALL_PASSED_YES
        if all(quality_fields.get(check) == PASS for check in QUALITY_CHECKS)
        else ALL_PASSED_NO
    )


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

    quality_fields = {
        "Mid Price": mid,
        "Spread": spread,
        "Spread %": spread_percent,
        "Strike Distance %": calculate_strike_distance_percent(
            contract.get("strike"), underlying_price
        ),
        "DTE": calculate_dte(expiration_value, today),
        "Delta Fit": delta_fit(option_type, delta),
        "Open Interest Pass": minimum_pass(contract.get("open_interest"), MIN_OPEN_INTEREST),
        "Volume Pass": minimum_pass(contract.get("volume"), MIN_VOLUME),
        "Spread Pass": spread_pass(spread_percent),
    }
    quality_fields["All Passed"] = all_quality_checks_pass(quality_fields)
    return quality_fields


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
