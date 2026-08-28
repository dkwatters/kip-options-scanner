"""Descriptive model performance scorecards; never investment advice."""
from __future__ import annotations

from collections import Counter, defaultdict
from statistics import mean, median
from typing import Iterable

from src.signal_outcomes import DEFAULT_HORIZONS, OutcomeFamily, OutcomeStatus, SignalOutcome
from src.signals import Signal, SignalFamily


def model_performance_scorecard(signals: Iterable[Signal], outcomes: Iterable[SignalOutcome], *, model_id: str, model_version: str, horizons: Iterable[int] = DEFAULT_HORIZONS) -> dict:
    """Return the unchanged v0.1 directional/return scorecard only."""
    selected = [s for s in signals if s.model_id == model_id and s.model_version == model_version and s.signal_family is SignalFamily.DIRECTIONAL]
    signal_ids = {s.signal_id for s in selected}
    selected_outcomes = [o for o in outcomes if o.signal_id in signal_ids and o.outcome_family is OutcomeFamily.RETURN]
    directions = Counter(s.direction.value for s in selected)
    by_horizon = defaultdict(dict)
    for outcome in selected_outcomes:
        by_horizon[outcome.horizon_trading_days][outcome.signal_id] = outcome
    horizon_results = {}
    for horizon in sorted(set(horizons) | set(by_horizon)):
        rows_by_signal = by_horizon[horizon]
        rows = list(rows_by_signal.values())
        evaluated = [row for row in rows if row.status is OutcomeStatus.EVALUATED]
        returns = [row.absolute_return for row in evaluated if row.absolute_return is not None]
        meaningful = [row.directional_correct for row in evaluated if row.directional_correct is not None]
        status_counts = Counter(row.status.value for row in rows)
        no_outcome_count = len(signal_ids - set(rows_by_signal))
        horizon_results[horizon] = {
            "evaluable_count": len(evaluated),
            "evaluated_count": status_counts[OutcomeStatus.EVALUATED.value],
            "missing_data_count": status_counts[OutcomeStatus.MISSING_DATA.value],
            "not_yet_eligible_count": status_counts[OutcomeStatus.NOT_YET_ELIGIBLE.value],
            "error_count": status_counts[OutcomeStatus.ERROR.value],
            "no_outcome_record_count": no_outcome_count,
            "missing_count": len(selected) - len(evaluated),
            "coverage": len(evaluated) / len(selected) if selected else 0.0,
            "directional_hit_rate": mean(meaningful) if meaningful else None,
            "directional_sample_count": len(meaningful),
            "average_forward_return": mean(returns) if returns else None,
            "median_forward_return": median(returns) if returns else None,
        }
    return {
        "model_id": model_id, "model_version": model_version,
        "signal_family": SignalFamily.DIRECTIONAL.value,
        "signal_count": len(selected),
        "direction_counts": {direction: directions.get(direction, 0) for direction in ("bullish", "neutral", "bearish", "abstain")},
        "horizons": horizon_results,
        "disclaimer": "Descriptive research evidence only; not investment advice.",
    }


def signal_family_summary(signals: Iterable[Signal]) -> dict[str, int]:
    counts = Counter(signal.signal_family.value for signal in signals)
    return {family.value: counts.get(family.value, 0) for family in SignalFamily}


def volatility_performance_scorecard(signals: Iterable[Signal], outcomes: Iterable[SignalOutcome]) -> dict:
    selected = [signal for signal in signals if signal.signal_family is SignalFamily.VOLATILITY]
    signal_ids = {signal.signal_id for signal in selected}
    regimes = Counter(str(signal.metadata.get("regime") or "unavailable") for signal in selected)
    trends = Counter(str(signal.metadata.get("volatility_trend") or "unavailable") for signal in selected)
    by_horizon = defaultdict(list)
    by_regime = defaultdict(list)
    for outcome in outcomes:
        if outcome.signal_id not in signal_ids or outcome.outcome_family is not OutcomeFamily.VOLATILITY:
            continue
        by_horizon[outcome.horizon_trading_days].append(outcome)
        if outcome.status is OutcomeStatus.EVALUATED and isinstance(outcome.components.get("realized_volatility"), (int, float)):
            by_regime[(outcome.horizon_trading_days, str(outcome.components.get("starting_regime") or "unavailable"))].append(float(outcome.components["realized_volatility"]))
    horizons = {}
    for horizon in sorted(set(DEFAULT_HORIZONS) | set(by_horizon)):
        rows = by_horizon[horizon]
        values = [float(row.components["realized_volatility"]) for row in rows if row.status is OutcomeStatus.EVALUATED and isinstance(row.components.get("realized_volatility"), (int, float))]
        horizons[horizon] = {"evaluated_count": len(values), "signal_count": len(selected),
                             "coverage": len(values) / len(selected) if selected else 0.0,
                             "average_realized_volatility": mean(values) if values else None,
                             "median_realized_volatility": median(values) if values else None}
    return {"signal_count": len(selected), "regime_counts": dict(regimes), "trend_counts": dict(trends),
            "horizons": horizons,
            "by_regime": {f"{horizon}d · {regime}": {"sample_count": len(values), "average_realized_volatility": mean(values), "median_realized_volatility": median(values)} for (horizon, regime), values in sorted(by_regime.items())},
            "disclaimer": "Descriptive research evidence only; no directional accuracy is asserted."}
