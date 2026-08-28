"""Deterministic, point-in-time volatility context calculations."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from math import log, sqrt
from statistics import pstdev, stdev
from typing import Iterable


ANNUALIZATION_FACTOR = 252
REALIZED_VOL_SHORT_WINDOW = 10
REALIZED_VOL_LONG_WINDOW = 20
ATR_WINDOW = 14
BOLLINGER_WINDOW = 20
BOLLINGER_STD_DEVS = 2.0
PERCENTILE_WINDOW = 252
MIN_PERCENTILE_OBSERVATIONS = 60
REGIME_DEFINITION = "rolling-vol-percentile-v0.1"
TREND_DEFINITION = "rv10-to-rv20-ratio-v0.1"


@dataclass(frozen=True, slots=True)
class DailyBar:
    trading_date: date
    high: float
    low: float
    close: float

    def __post_init__(self) -> None:
        if min(self.high, self.low, self.close) <= 0 or self.high < self.low:
            raise ValueError("daily OHLC values must be positive and high must be >= low")


def realized_volatility(closes: Iterable[float], period: int) -> float | None:
    values = tuple(closes)
    if period <= 1 or len(values) <= period:
        return None
    returns = [log(values[index] / values[index - 1]) for index in range(len(values) - period, len(values))]
    return stdev(returns) * sqrt(ANNUALIZATION_FACTOR)


def atr_percent(bars: Iterable[DailyBar], period: int = ATR_WINDOW) -> float | None:
    rows = tuple(bars)
    if len(rows) <= period:
        return None
    true_ranges = []
    for index in range(len(rows) - period, len(rows)):
        row, previous_close = rows[index], rows[index - 1].close
        true_ranges.append(max(row.high - row.low, abs(row.high - previous_close), abs(row.low - previous_close)))
    return (sum(true_ranges) / period) / rows[-1].close


def bollinger_bandwidth(closes: Iterable[float], period: int = BOLLINGER_WINDOW) -> float | None:
    values = tuple(closes)
    if len(values) < period:
        return None
    sample = values[-period:]
    middle = sum(sample) / period
    if middle <= 0:
        return None
    return (2 * BOLLINGER_STD_DEVS * pstdev(sample)) / middle


def rolling_realized_volatility(closes: Iterable[float], period: int = REALIZED_VOL_LONG_WINDOW) -> tuple[float, ...]:
    values = tuple(closes)
    return tuple(
        value for end in range(period + 1, len(values) + 1)
        if (value := realized_volatility(values[:end], period)) is not None
    )


def volatility_percentile(observations: Iterable[float], *, window: int = PERCENTILE_WINDOW) -> float | None:
    values = tuple(observations)[-window:]
    if len(values) < MIN_PERCENTILE_OBSERVATIONS:
        return None
    current = values[-1]
    return 100.0 * sum(value <= current for value in values) / len(values)


def classify_regime(percentile: float | None) -> str | None:
    if percentile is None:
        return None
    if percentile < 25:
        return "quiet"
    if percentile < 70:
        return "normal"
    if percentile < 90:
        return "elevated"
    return "extreme"


def classify_volatility_trend(rv10: float | None, rv20: float | None) -> str | None:
    if rv10 is None or rv20 is None or rv20 <= 0:
        return None
    ratio = rv10 / rv20
    if ratio > 1.10:
        return "expanding"
    if ratio < 0.90:
        return "contracting"
    return "stable"


def calculate_volatility_context(bars: Iterable[DailyBar]) -> dict:
    rows_by_date = {row.trading_date: row for row in bars}
    rows = tuple(rows_by_date[key] for key in sorted(rows_by_date))
    closes = tuple(row.close for row in rows)
    rv10 = realized_volatility(closes, REALIZED_VOL_SHORT_WINDOW)
    rv20 = realized_volatility(closes, REALIZED_VOL_LONG_WINDOW)
    history = rolling_realized_volatility(closes)
    percentile = volatility_percentile(history)
    sufficient = percentile is not None
    return {
        "components": {
            "realized_volatility_10d": rv10,
            "realized_volatility_20d": rv20,
            "atr_pct_14d": atr_percent(rows),
            "bollinger_bandwidth_20d": bollinger_bandwidth(closes),
            "volatility_percentile": percentile,
        },
        "metadata": {
            "regime": classify_regime(percentile),
            "volatility_trend": classify_volatility_trend(rv10, rv20),
            "regime_definition": REGIME_DEFINITION,
            "trend_definition": TREND_DEFINITION,
            "history_start": rows[0].trading_date.isoformat() if rows else None,
            "history_end": rows[-1].trading_date.isoformat() if rows else None,
            "observation_count": len(rows),
            "percentile_observation_count": min(len(history), PERCENTILE_WINDOW),
            "data_quality": "sufficient_history" if sufficient else "partial_history",
            "insufficient_history": not sufficient,
            "annualization_factor": ANNUALIZATION_FACTOR,
        },
    }
