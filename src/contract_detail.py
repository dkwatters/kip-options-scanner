"""Presentation-neutral detail data for one evaluated option contract."""
from typing import Any

from src.contract_quality import (
    CALL_DELTA_RANGE,
    MAX_SPREAD_PERCENT,
    MIN_OPEN_INTEREST,
    MIN_VOLUME,
    PUT_DELTA_RANGE,
)
from src.rule_evaluation import FAIL, NOT_AVAILABLE, PASS


SUMMARY_FIELDS = (
    ("Contract", "Contract"),
    ("Contract Symbol", "Symbol"),
    ("Option Type", "Option Type"),
    ("Strike", "Strike"),
    ("Expiration", "Expiration"),
    ("DTE", "DTE"),
    ("Bid", "Bid"),
    ("Ask", "Ask"),
    ("Mid Price", "Mid Price"),
    ("Spread %", "Spread %"),
    ("Delta", "Delta"),
    ("IV", "IV"),
    ("Open Interest", "Open Interest"),
    ("Volume", "Volume"),
    ("All Passed", "All Passed"),
    ("Failed Tests", "Failed Tests"),
)


def _delta_requirement(option_type: Any) -> str:
    """Return the delta range applicable to a displayed option type."""
    option_type = option_type.lower() if isinstance(option_type, str) else ""
    ranges = {"call": CALL_DELTA_RANGE, "put": PUT_DELTA_RANGE}
    minimum, maximum = ranges.get(option_type, (None, None))
    return f"{minimum:.2f} to {maximum:.2f}" if minimum is not None else NOT_AVAILABLE


def contract_detail_fields(row: dict[str, Any]) -> dict[str, Any]:
    """Return the required high-level fields for one display-ready contract."""
    return {label: row.get(source, NOT_AVAILABLE) for label, source in SUMMARY_FIELDS}


def contract_rule_explanations(row: dict[str, Any]) -> list[dict[str, Any]]:
    """Return each current quality rule with its decision inputs and margin."""
    return [
        {
            "Rule": "Delta Fit",
            "Pass/Fail": row.get("Delta Fit", NOT_AVAILABLE),
            "Actual Value": row.get("Delta", NOT_AVAILABLE),
            "Required Value": _delta_requirement(row.get("Option Type")),
            "Margin": row.get("Delta Margin", NOT_AVAILABLE),
        },
        {
            "Rule": "Spread",
            "Pass/Fail": row.get("Spread Pass", NOT_AVAILABLE),
            "Actual Value": row.get("Spread %", NOT_AVAILABLE),
            "Required Value": MAX_SPREAD_PERCENT,
            "Margin": row.get("Spread Margin", NOT_AVAILABLE),
        },
        {
            "Rule": "Open Interest",
            "Pass/Fail": row.get("Open Interest Pass", NOT_AVAILABLE),
            "Actual Value": row.get("Open Interest", NOT_AVAILABLE),
            "Required Value": MIN_OPEN_INTEREST,
            "Margin": row.get("OI Margin", NOT_AVAILABLE),
        },
        {
            "Rule": "Volume",
            "Pass/Fail": row.get("Volume Pass", NOT_AVAILABLE),
            "Actual Value": row.get("Volume", NOT_AVAILABLE),
            "Required Value": MIN_VOLUME,
            "Margin": row.get("Volume Margin", NOT_AVAILABLE),
        },
    ]


def contract_interpretation(row: dict[str, Any]) -> str:
    """Describe the current quality outcomes without implying a trade action."""
    labels = (
        ("Delta Fit", "delta"),
        ("Spread Pass", "spread"),
        ("Open Interest Pass", "open interest"),
        ("Volume Pass", "volume"),
    )
    passed = [label for check, label in labels if row.get(check) == PASS]
    failed = [label for check, label in labels if row.get(check) == FAIL]
    unavailable = [
        label for check, label in labels if row.get(check) not in {PASS, FAIL}
    ]

    def joined(items: list[str]) -> str:
        if len(items) <= 2:
            return " and ".join(items)
        return ", ".join(items[:-1]) + f", and {items[-1]}"

    def requirement_word(items: list[str]) -> str:
        return "requirement" if len(items) == 1 else "requirements"

    if not failed and not unavailable:
        return "This contract passes all current quality requirements."

    sentences = []
    if passed:
        sentences.append(
            f"This contract passes {joined(passed)} {requirement_word(passed)}"
        )
    else:
        sentences.append("This contract does not pass any evaluated quality requirements")
    if failed:
        sentences[-1] += f" but fails {joined(failed)} {requirement_word(failed)}"
    sentences[-1] += "."
    if unavailable:
        sentences.append(f"{joined(unavailable).capitalize()} data is unavailable for evaluation.")
    return " ".join(sentences)
