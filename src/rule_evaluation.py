"""Reusable rule evaluation models and comparison helpers.

These objects contain the values used to make a rule decision so consumers can
show concise explanations without reimplementing the underlying comparison.
"""
from dataclasses import dataclass
from math import isfinite
from typing import Any


PASS = "Pass"
FAIL = "Fail"
NOT_AVAILABLE = "N/A"


def _number(value: Any) -> float | None:
    """Return a finite numeric value, or ``None`` when it is unavailable."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if isfinite(number) else None


def _display_value(value: Any) -> str:
    """Render values compactly for UI-facing rule detail text."""
    if value == NOT_AVAILABLE or value is None:
        return NOT_AVAILABLE
    try:
        return f"{float(value):,.2f}"
    except (TypeError, ValueError):
        pass
    return str(value)


def _display_percent(value: Any) -> str:
    """Render decimal percentage values for UI-facing rule detail text."""
    if value == NOT_AVAILABLE or value is None:
        return NOT_AVAILABLE
    try:
        return f"{float(value):.2%}"
    except (TypeError, ValueError):
        return str(value)


def _display_count(value: Any) -> str:
    """Render contract counts without decimal places."""
    if value == NOT_AVAILABLE or value is None:
        return NOT_AVAILABLE
    try:
        return f"{float(value):,.0f}"
    except (TypeError, ValueError):
        return str(value)


@dataclass(frozen=True)
class RuleEvaluation:
    """The complete outcome of one reusable contract-quality rule."""

    rule_name: str
    actual_value: Any
    required_value: Any
    margin: float | str
    result: str

    def detail(self) -> str:
        """Return a compact, display-ready explanation of the rule outcome."""
        if self.rule_name == "Spread %":
            formatter = _display_percent
        elif self.rule_name in {"Open Interest", "Volume"}:
            formatter = _display_count
        else:
            formatter = _display_value
        return (
            f"Actual {formatter(self.actual_value)} / "
            f"Required {formatter(self.required_value)} / "
            f"Margin {formatter(self.margin)}"
        )


def evaluate_minimum(rule_name: str, actual_value: Any, minimum: float) -> RuleEvaluation:
    """Evaluate whether a numeric actual value meets a minimum requirement."""
    actual = _number(actual_value)
    if actual is None:
        return RuleEvaluation(rule_name, NOT_AVAILABLE, minimum, NOT_AVAILABLE, NOT_AVAILABLE)
    margin = actual - minimum
    return RuleEvaluation(rule_name, actual, minimum, margin, PASS if margin >= 0 else FAIL)


def evaluate_maximum(rule_name: str, actual_value: Any, maximum: float) -> RuleEvaluation:
    """Evaluate whether a numeric actual value stays at or below a maximum."""
    actual = _number(actual_value)
    if actual is None:
        return RuleEvaluation(rule_name, NOT_AVAILABLE, maximum, NOT_AVAILABLE, NOT_AVAILABLE)
    margin = maximum - actual
    return RuleEvaluation(rule_name, actual, maximum, margin, PASS if margin >= 0 else FAIL)


def evaluate_range(
    rule_name: str, actual_value: Any, minimum: float, maximum: float
) -> RuleEvaluation:
    """Evaluate whether a numeric actual value falls inside an inclusive range."""
    actual = _number(actual_value)
    required = f"{minimum:g} to {maximum:g}"
    if actual is None:
        return RuleEvaluation(rule_name, NOT_AVAILABLE, required, NOT_AVAILABLE, NOT_AVAILABLE)
    margin = min(actual - minimum, maximum - actual)
    return RuleEvaluation(rule_name, actual, required, margin, PASS if margin >= 0 else FAIL)
