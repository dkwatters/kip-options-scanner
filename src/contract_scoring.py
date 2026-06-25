"""Transparent, configurable quality scoring for evaluated option contracts.

This module scores existing rule outcomes and margins only. It does not select,
rank, or recommend contracts.
"""
from math import isfinite
from typing import Any, Mapping

from src.rule_evaluation import FAIL, PASS


QUALITY_WEIGHTS = {
    "Delta Fit": 30,
    "Spread": 30,
    "Open Interest": 20,
    "Volume": 20,
}

# This structure is intentionally separate from the scoring calculation so the
# values can become user-editable without changing the scoring implementation.
QUALITY_SCORE_CONFIG = {
    "weights": QUALITY_WEIGHTS,
    "passing_floor": 0.80,
    "failing_ceiling": 0.75,
    "rules": {
        "Delta Fit": {"check": "Delta Fit", "margin": "Delta Margin", "scale": 0.10},
        "Spread": {"check": "Spread Pass", "margin": "Spread Margin", "scale": 0.05},
        "Open Interest": {
            "check": "Open Interest Pass",
            "margin": "OI Margin",
            "scale": 1_000,
        },
        "Volume": {"check": "Volume Pass", "margin": "Volume Margin", "scale": 500},
    },
}


def _number(value: Any) -> float | None:
    """Return a finite numeric value, or None when unavailable."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if isfinite(number) else None


def validate_quality_score_config(config: Mapping[str, Any]) -> None:
    """Validate the public scoring configuration before it is used."""
    weights = config.get("weights")
    rules = config.get("rules")
    if not isinstance(weights, Mapping) or not isinstance(rules, Mapping):
        raise ValueError("Quality score configuration requires weights and rules mappings.")
    if set(weights) != set(rules):
        raise ValueError("Quality score weights and rules must use the same rule names.")
    if any(_number(weight) is None or _number(weight) < 0 for weight in weights.values()):
        raise ValueError("Quality score weights must be non-negative finite numbers.")
    if sum(float(weight) for weight in weights.values()) != 100:
        raise ValueError("Quality score weights must total 100.")
    band_values = {}
    for setting in ("passing_floor", "failing_ceiling"):
        value = _number(config.get(setting))
        if value is None or not 0 <= value <= 1:
            raise ValueError(f"Quality score {setting} must be between 0 and 1.")
        band_values[setting] = value
    if band_values["passing_floor"] <= band_values["failing_ceiling"]:
        raise ValueError("The passing floor must exceed the failing ceiling.")
    for rule_name, rule in rules.items():
        if not isinstance(rule, Mapping) or _number(rule.get("scale")) is None:
            raise ValueError(f"Quality score rule {rule_name} requires a positive scale.")
        if float(rule["scale"]) <= 0:
            raise ValueError(f"Quality score rule {rule_name} requires a positive scale.")


def _points_for_rule(result: Any, margin: Any, weight: float, scale: float, config: Mapping[str, Any]) -> int:
    """Return earned points for one rule from its existing outcome and margin."""
    numeric_margin = _number(margin)
    if numeric_margin is None:
        return 0
    closeness = min(max(abs(numeric_margin) / scale, 0), 1)
    if result == PASS:
        proportion = float(config["passing_floor"]) + (
            (1 - float(config["passing_floor"])) * closeness
        )
    elif result == FAIL:
        proportion = float(config["failing_ceiling"]) * (1 - closeness)
    else:
        return 0
    return round(weight * proportion)


def contract_quality_score(
    row: Mapping[str, Any], config: Mapping[str, Any] = QUALITY_SCORE_CONFIG
) -> dict[str, Any]:
    """Return a total score and rule-by-rule breakdown for an evaluated contract.

    Passing rules use the upper score band, from the configured passing floor to
    the full rule weight. Failing rules use the lower band and lose points as
    their negative margin grows. This preserves the existing rule decisions
    while ensuring a passing rule scores above an otherwise-identical failure.
    """
    validate_quality_score_config(config)
    breakdown = []
    for label, rule in config["rules"].items():
        weight = float(config["weights"][label])
        points = _points_for_rule(
            row.get(rule["check"]),
            row.get(rule["margin"]),
            weight,
            float(rule["scale"]),
            config,
        )
        breakdown.append(
            {
                "Rule": label,
                "Points": points,
                "Weight": round(weight),
                "Pass/Fail": row.get(rule["check"], "N/A"),
                "Margin": row.get(rule["margin"], "N/A"),
            }
        )
    return {
        "Quality Score": sum(item["Points"] for item in breakdown),
        "Quality Score Breakdown": breakdown,
    }
