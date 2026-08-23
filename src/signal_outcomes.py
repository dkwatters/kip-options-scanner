"""Point-in-time-safe forward outcome evaluation, separate from signal generation."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from enum import Enum
from typing import Iterable, Protocol

from src.signals import Signal, SignalDirection

DEFAULT_HORIZONS = (5, 20, 60)


class OutcomeStatus(str, Enum):
    EVALUATED = "evaluated"
    MISSING_DATA = "missing_data"
    NOT_YET_ELIGIBLE = "not_yet_eligible"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class PriceObservation:
    trading_date: date
    close: float

    def __post_init__(self) -> None:
        if self.close <= 0:
            raise ValueError("close must be positive")


@dataclass(frozen=True, slots=True)
class SignalOutcome:
    signal_id: str
    horizon_trading_days: int
    status: OutcomeStatus
    start_date: str | None = None
    end_date: str | None = None
    start_price: float | None = None
    end_price: float | None = None
    absolute_return: float | None = None
    directional_correct: bool | None = None
    error: str | None = None
    evaluated_at: str = ""


class HistoricalPriceProvider(Protocol):
    """Market-data boundary; implementations must return point-in-time dated closes."""

    def daily_closes(self, ticker: str, *, on_or_after: date) -> Iterable[PriceObservation]: ...


def evaluate_signal_outcome(
    signal: Signal,
    observations: Iterable[PriceObservation],
    horizon: int,
    *,
    through_date: date | None = None,
    evaluated_at: str | None = None,
) -> SignalOutcome:
    """Use the first close on/after as-of and the Nth subsequent trading close."""
    if horizon <= 0:
        raise ValueError("horizon must be a positive trading-day count")
    stamp = evaluated_at or datetime.now(timezone.utc).isoformat()
    try:
        as_of_date = date.fromisoformat(signal.as_of[:10])
        rows = sorted({row.trading_date: row for row in observations}.values(), key=lambda row: row.trading_date)
        rows = [row for row in rows if row.trading_date >= as_of_date]
        if not rows:
            return SignalOutcome(signal.signal_id, horizon, OutcomeStatus.MISSING_DATA, error="No starting observation on or after signal as-of date.", evaluated_at=stamp)
        start = rows[0]
        end_index = horizon
        if len(rows) <= end_index:
            status = OutcomeStatus.NOT_YET_ELIGIBLE if through_date is not None and rows[-1].trading_date >= through_date else OutcomeStatus.MISSING_DATA
            return SignalOutcome(signal.signal_id, horizon, status, start_date=start.trading_date.isoformat(), start_price=start.close, error="Insufficient subsequent trading-day observations.", evaluated_at=stamp)
        end = rows[end_index]
        result = (end.close / start.close) - 1.0
        correctness = None
        if signal.direction is SignalDirection.BULLISH:
            correctness = result > 0
        elif signal.direction is SignalDirection.BEARISH:
            correctness = result < 0
        return SignalOutcome(
            signal.signal_id, horizon, OutcomeStatus.EVALUATED,
            start.trading_date.isoformat(), end.trading_date.isoformat(),
            start.close, end.close, result, correctness, evaluated_at=stamp,
        )
    except Exception as error:
        return SignalOutcome(signal.signal_id, horizon, OutcomeStatus.ERROR, error=str(error), evaluated_at=stamp)


def evaluate_signal_horizons(signal: Signal, observations: Iterable[PriceObservation], horizons: Iterable[int] = DEFAULT_HORIZONS, **kwargs) -> tuple[SignalOutcome, ...]:
    rows = tuple(observations)
    return tuple(evaluate_signal_outcome(signal, rows, horizon, **kwargs) for horizon in horizons)


def evaluate_persisted_signal(repository, signal_id: str, price_provider: HistoricalPriceProvider, *, horizons: Iterable[int] = DEFAULT_HORIZONS, **kwargs) -> tuple[SignalOutcome, ...]:
    """Load one immutable signal, deliberately inspect later prices, and persist outcomes."""
    matches = tuple(signal for signal in repository.list_signals() if signal.signal_id == signal_id)
    if not matches:
        raise LookupError(f"Unknown signal_id: {signal_id}")
    signal = matches[0]
    observations = tuple(price_provider.daily_closes(signal.ticker, on_or_after=date.fromisoformat(signal.as_of[:10])))
    outcomes = evaluate_signal_horizons(signal, observations, horizons=horizons, **kwargs)
    repository.save_outcomes(outcomes)
    return outcomes
