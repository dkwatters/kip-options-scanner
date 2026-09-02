from datetime import date, timedelta
from math import sqrt

import pytest

from src.signal_outcomes import OutcomeFamily, OutcomeStatus, PriceObservation, evaluate_signal_horizons
from src.signals import SignalDirection, SignalFamily, volatility_context_signal
from src.market_calendar import is_us_equity_trading_day
from src.technical_analysis import (
    most_recent_completed_trading_session, technical_analysis_rows_for_symbols,
)
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


def _provider_days(through, count=120):
    days, candidate = [], through
    while len(days) < count:
        if is_us_equity_trading_day(candidate):
            index = count - len(days)
            days.append({"date": candidate.isoformat(), "high": 101 + index * .1,
                         "low": 99 + index * .1, "close": 100 + index * .1})
        candidate -= timedelta(days=1)
    return list(reversed(days))


def _live_context(days, as_of):
    class Client:
        def get_price_history(self, *args, **kwargs):
            return {"history": {"day": days}}

        def get_quote(self, *args, **kwargs):
            return {"quotes": {"quote": {"last": 250}}}

    rows, errors = technical_analysis_rows_for_symbols(
        Client(), ["SPY"], scan_id="live", technical_timestamp=f"{as_of} 12:00 PM EDT",
        end_date=as_of, current_date=as_of,
    )
    assert not errors
    return rows[0]


def test_same_day_extreme_bar_cannot_change_volatility_context():
    as_of = date(2026, 8, 27)
    completed = most_recent_completed_trading_session(as_of)
    history = _provider_days(completed)
    baseline = _live_context(history, as_of)
    with_extreme = _live_context(
        history + [{"date": as_of.isoformat(), "high": 10000, "low": 1, "close": 9000}],
        as_of,
    )
    assert with_extreme["_volatility_context"] == baseline["_volatility_context"]
    assert with_extreme["_volatility_context"]["metadata"]["history_end"] == completed.isoformat()
    assert set(with_extreme["_volatility_context"]["components"]) == {
        "realized_volatility_10d", "realized_volatility_20d", "atr_pct_14d",
        "bollinger_bandwidth_20d", "volatility_percentile",
    }
    assert with_extreme["_volatility_context"]["metadata"]["regime"] == baseline["_volatility_context"]["metadata"]["regime"]
    assert with_extreme["_volatility_context"]["metadata"]["volatility_trend"] == baseline["_volatility_context"]["metadata"]["volatility_trend"]


def test_completed_session_boundary_handles_weekend_and_holiday():
    assert most_recent_completed_trading_session(date(2026, 7, 11)) == date(2026, 7, 10)
    assert most_recent_completed_trading_session(date(2026, 7, 3)) == date(2026, 7, 2)
    weekend_row = _live_context(
        _provider_days(date(2026, 7, 10)) + [
            {"date": "2026-07-11", "high": 999, "low": 1, "close": 500}
        ], date(2026, 7, 11),
    )
    holiday_row = _live_context(
        _provider_days(date(2026, 7, 2)) + [
            {"date": "2026-07-03", "high": 999, "low": 1, "close": 500}
        ], date(2026, 7, 3),
    )
    assert weekend_row["_volatility_context"]["metadata"]["history_end"] == "2026-07-10"
    assert holiday_row["_volatility_context"]["metadata"]["history_end"] == "2026-07-02"


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
