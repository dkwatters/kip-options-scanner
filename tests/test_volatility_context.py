from datetime import date, timedelta
from math import sqrt

import pytest

from src.signal_outcomes import OutcomeFamily, OutcomeStatus, PriceObservation, evaluate_signal_horizons
from src.signals import SignalDirection, SignalFamily, volatility_context_signal
from src.volatility_context import (
    DailyBar, atr_percent, bollinger_bandwidth, calculate_volatility_context,
    classify_regime, classify_volatility_trend, realized_volatility,
    volatility_percentile,
)


def bars(count=300):
    start = date(2024, 1, 2)
    return [DailyBar(start + timedelta(days=index), 101 + index * .1, 99 + index * .1,
                     100 + index * .1 + ((index % 7) - 3) * .2) for index in range(count)]


def test_calculations_and_classification_boundaries():
    closes = [row.close for row in bars(40)]
    daily = realized_volatility(closes, 20) / sqrt(252)
    assert realized_volatility(closes, 20) == pytest.approx(daily * sqrt(252))
    assert atr_percent(bars(20), 14) > 0
    assert bollinger_bandwidth(closes, 20) > 0
    assert volatility_percentile(range(1, 61)) == 100
    assert [classify_regime(value) for value in (24.99, 25, 69.99, 70, 89.99, 90)] == ["quiet", "normal", "normal", "elevated", "elevated", "extreme"]
    assert classify_volatility_trend(.22, .20) == "stable"
    assert classify_volatility_trend(.221, .20) == "expanding"
    assert classify_volatility_trend(.179, .20) == "contracting"


def test_context_and_signal_are_point_in_time_deterministic():
    history = bars()
    first_context = calculate_volatility_context(history[:280])
    future_changed = calculate_volatility_context(history[:280] + [DailyBar(date(2030, 1, 1), 999, 1, 500)])
    replay_again = calculate_volatility_context([row for row in history + [DailyBar(date(2030, 1, 1), 999, 1, 500)] if row.trading_date <= history[279].trading_date])
    assert first_context == replay_again
    assert future_changed != first_context
    row = {"ticker": "nvda", "technical_timestamp": "2025-01-31", "scan_id": "scan", "_volatility_context": first_context}
    first = volatility_context_signal(row)
    assert first == volatility_context_signal(row)
    assert first.signal_family is SignalFamily.VOLATILITY
    assert first.direction is SignalDirection.NOT_APPLICABLE
    assert first.conviction == 0 and first.confidence is None
    assert first.metadata["history_end"] <= "2025-01-31"


def _weekday_prices(start, sessions):
    rows, day = [], start
    while len(rows) < sessions:
        if day.weekday() < 5 and day != date(2026, 1, 19):
            rows.append(PriceObservation(day, 100 + len(rows) + (len(rows) % 2)))
        day += timedelta(days=1)
    return rows


def test_volatility_outcomes_use_verified_sessions_and_no_directional_correctness():
    context = calculate_volatility_context(bars())
    signal = volatility_context_signal({"ticker": "NVDA", "technical_timestamp": "2026-01-16", "scan_id": "scan", "_volatility_context": context})
    observations = _weekday_prices(date(2026, 1, 16), 70)
    outcomes = evaluate_signal_horizons(signal, observations, through_date=observations[-1].trading_date)
    assert [row.horizon_trading_days for row in outcomes] == [5, 20, 60]
    assert all(row.status is OutcomeStatus.EVALUATED for row in outcomes)
    assert all(row.outcome_family is OutcomeFamily.VOLATILITY and row.directional_correct is None for row in outcomes)
    assert outcomes[0].end_date == "2026-01-26"  # weekend and MLK Day excluded
    missing = evaluate_signal_horizons(signal, observations[:4], horizons=(5,), through_date=date(2026, 2, 1))[0]
    assert missing.status is OutcomeStatus.MISSING_DATA
    immature = evaluate_signal_horizons(signal, observations[:4], horizons=(20,), through_date=observations[3].trading_date)[0]
    assert immature.status is OutcomeStatus.NOT_YET_ELIGIBLE
