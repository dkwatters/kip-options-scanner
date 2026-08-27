"""Point-in-time-safe forward outcome evaluation, separate from signal generation."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from enum import Enum
from typing import Any, Iterable, Mapping, Protocol

from src.signals import Signal, SignalDirection, SignalFamily
from src.market_calendar import is_us_equity_trading_day

DEFAULT_HORIZONS = (5, 20, 60)


class OutcomeStatus(str, Enum):
    EVALUATED = "evaluated"
    MISSING_DATA = "missing_data"
    NOT_YET_ELIGIBLE = "not_yet_eligible"
    ERROR = "error"


class OutcomeFamily(str, Enum):
    RETURN = "return"
    VOLATILITY = "volatility"


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
    outcome_family: OutcomeFamily = OutcomeFamily.RETURN
    components: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        try:
            family = OutcomeFamily(self.outcome_family)
        except ValueError as error:
            raise ValueError(f"Unsupported outcome family: {self.outcome_family}") from error
        object.__setattr__(self, "outcome_family", family)
        if family is OutcomeFamily.VOLATILITY and self.directional_correct is not None:
            raise ValueError("volatility outcomes cannot have directional correctness")


SIGNAL_OUTCOME_COMPATIBILITY = {
    SignalFamily.DIRECTIONAL: OutcomeFamily.RETURN,
    SignalFamily.VOLATILITY: OutcomeFamily.VOLATILITY,
}


def compatible_outcome_family(signal: Signal) -> OutcomeFamily:
    return SIGNAL_OUTCOME_COMPATIBILITY[signal.signal_family]


def validate_signal_outcome_compatibility(signal: Signal, outcome: SignalOutcome) -> None:
    expected = compatible_outcome_family(signal)
    if outcome.outcome_family is not expected:
        raise ValueError(
            f"{signal.signal_family.value} signals require {expected.value} outcomes"
        )


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
    if signal.signal_family is not SignalFamily.DIRECTIONAL:
        raise ValueError("return outcome evaluation requires a directional signal")
    if horizon <= 0:
        raise ValueError("horizon must be a positive trading-day count")
    stamp = evaluated_at or datetime.now(timezone.utc).isoformat()
    try:
        as_of_date = date.fromisoformat(signal.as_of[:10])
        rows_by_date: dict[date, PriceObservation] = {}
        for row in observations:
            if row.trading_date in rows_by_date:
                raise ValueError(f"Duplicate price observation for {row.trading_date.isoformat()}.")
            if is_us_equity_trading_day(row.trading_date):
                rows_by_date[row.trading_date] = row
        expected_start = _trading_day_on_or_after(as_of_date)
        start = rows_by_date.get(expected_start)
        if start is None:
            status = (
                OutcomeStatus.NOT_YET_ELIGIBLE
                if through_date is not None and expected_start > through_date
                else OutcomeStatus.MISSING_DATA
            )
            return SignalOutcome(signal.signal_id, horizon, status, error=f"Missing required starting session observation for {expected_start.isoformat()}.", evaluated_at=stamp)
        required_dates = _trading_session_dates(expected_start, horizon)
        expected_end = required_dates[-1]
        if through_date is not None and expected_end > through_date:
            return SignalOutcome(signal.signal_id, horizon, OutcomeStatus.NOT_YET_ELIGIBLE, start_date=start.trading_date.isoformat(), start_price=start.close, error=f"Horizon matures on {expected_end.isoformat()}.", evaluated_at=stamp)
        missing_dates = [session for session in required_dates if session not in rows_by_date]
        if missing_dates:
            return SignalOutcome(signal.signal_id, horizon, OutcomeStatus.MISSING_DATA, start_date=start.trading_date.isoformat(), start_price=start.close, error="Missing required trading-session observations: " + ", ".join(session.isoformat() for session in missing_dates), evaluated_at=stamp)
        end = rows_by_date[expected_end]
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


def _trading_day_on_or_after(day: date) -> date:
    while not is_us_equity_trading_day(day):
        day += timedelta(days=1)
    return day


def _trading_session_dates(start: date, horizon: int) -> tuple[date, ...]:
    sessions = [start]
    candidate = start
    while len(sessions) <= horizon:
        candidate += timedelta(days=1)
        if is_us_equity_trading_day(candidate):
            sessions.append(candidate)
    return tuple(sessions)


def evaluate_signal_horizons(signal: Signal, observations: Iterable[PriceObservation], horizons: Iterable[int] = DEFAULT_HORIZONS, **kwargs) -> tuple[SignalOutcome, ...]:
    rows = tuple(observations)
    return tuple(evaluate_signal_outcome(signal, rows, horizon, **kwargs) for horizon in horizons)


def evaluate_persisted_signal(repository, signal_id: str, price_provider: HistoricalPriceProvider, *, horizons: Iterable[int] = DEFAULT_HORIZONS, **kwargs) -> tuple[SignalOutcome, ...]:
    """Load one immutable signal, deliberately inspect later prices, and persist outcomes."""
    matches = tuple(signal for signal in repository.list_signals() if signal.signal_id == signal_id)
    if not matches:
        raise LookupError(f"Unknown signal_id: {signal_id}")
    signal = matches[0]
    if compatible_outcome_family(signal) is not OutcomeFamily.RETURN:
        raise ValueError(
            f"{signal.signal_family.value} signals are not compatible with return outcome evaluation"
        )
    observations = tuple(price_provider.daily_closes(signal.ticker, on_or_after=date.fromisoformat(signal.as_of[:10])))
    outcomes = evaluate_signal_horizons(signal, observations, horizons=horizons, **kwargs)
    repository.save_outcomes(outcomes)
    return outcomes
