"""Descriptive model performance scorecards; never investment advice."""
from __future__ import annotations

from collections import Counter, defaultdict
from statistics import mean, median
from typing import Iterable

from src.signal_outcomes import OutcomeStatus, SignalOutcome
from src.signals import Signal


def model_performance_scorecard(signals: Iterable[Signal], outcomes: Iterable[SignalOutcome], *, model_id: str, model_version: str) -> dict:
    selected = [s for s in signals if s.model_id == model_id and s.model_version == model_version]
    signal_ids = {s.signal_id for s in selected}
    selected_outcomes = [o for o in outcomes if o.signal_id in signal_ids]
    directions = Counter(s.direction.value for s in selected)
    by_horizon = defaultdict(list)
    for outcome in selected_outcomes:
        by_horizon[outcome.horizon_trading_days].append(outcome)
    horizons = {}
    for horizon, rows in sorted(by_horizon.items()):
        evaluated = [row for row in rows if row.status is OutcomeStatus.EVALUATED]
        returns = [row.absolute_return for row in evaluated if row.absolute_return is not None]
        meaningful = [row.directional_correct for row in evaluated if row.directional_correct is not None]
        horizons[horizon] = {
            "evaluable_count": len(evaluated),
            "missing_count": len(rows) - len(evaluated),
            "coverage": len(evaluated) / len(rows) if rows else 0.0,
            "directional_hit_rate": mean(meaningful) if meaningful else None,
            "directional_sample_count": len(meaningful),
            "average_forward_return": mean(returns) if returns else None,
            "median_forward_return": median(returns) if returns else None,
        }
    return {
        "model_id": model_id, "model_version": model_version,
        "signal_count": len(selected),
        "direction_counts": {direction: directions.get(direction, 0) for direction in ("bullish", "neutral", "bearish", "abstain")},
        "horizons": horizons,
        "disclaimer": "Descriptive research evidence only; not investment advice.",
    }
