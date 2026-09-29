"""Explicit research-only GARCH path; normal scans incur no extra I/O or fitting."""
from datetime import date, datetime, timedelta
from time import perf_counter
from zoneinfo import ZoneInfo
from src.garch_challenger import (fit_garch, signal_identity, GarchResult, MODEL_ID, MODEL_VERSION, HISTORY_CALENDAR_DAYS)
from src.technical_analysis import most_recent_completed_trading_session
from src.observation_event_repository import ObservationEventRepository
from src.scheduled_observation_engine import observe_signal_changes
from src.signal_outcomes import PriceObservation, evaluate_signal_horizons
from src.technical_observation_service import safe_diagnostic_detail
from src.market_calendar import is_us_equity_trading_day


def run_garch_research(ticker, as_of, *, client, repository):
    started = perf_counter()
    if as_of > datetime.now(ZoneInfo("America/New_York")).date():
        return GarchResult(None, "provider_history_failure", {"error": "Future analysis dates are not supported"})
    existing = next((s for s in repository.list_signals(ticker=ticker.strip().upper(), model_id=MODEL_ID, model_version=MODEL_VERSION)
                     if s.signal_id == signal_identity(ticker, as_of)), None)
    if existing is not None:
        # Do not fetch or refit an immutable historical forecast. Recover a missing comparison only.
        observe_signal_changes((existing,), signal_repository=repository, event_repository=ObservationEventRepository(repository.target))
        return GarchResult(existing, "retry", {"elapsed_seconds": perf_counter()-started, "refitted": False})
    try:
        payload = client.get_price_history(ticker.strip().upper(), start=(as_of-timedelta(days=HISTORY_CALENDAR_DAYS)).isoformat(),
                                           end=most_recent_completed_trading_session(as_of).isoformat())
    except Exception as error:
        return GarchResult(None, "provider_history_failure", {"error": safe_diagnostic_detail(error)})
    result = fit_garch(ticker, as_of, payload)
    if result.signal is not None:
        repository.save_signal(result.signal)
        observe_signal_changes((result.signal,), signal_repository=repository, event_repository=ObservationEventRepository(repository.target))
    return GarchResult(result.signal, result.status, {**result.diagnostics, "elapsed_seconds": perf_counter()-started})


def evaluate_garch_history(signals, *, client, repository, through_date=None):
    """Explicitly refresh only future Outcomes, never refit historical forecasts."""
    completed = most_recent_completed_trading_session(datetime.now(ZoneInfo("America/New_York")).date())
    cutoff = min(through_date, completed) if through_date is not None else completed
    results = []
    for signal in signals:
        if signal.model_id != MODEL_ID or signal.model_version != MODEL_VERSION:
            continue
        payload = client.get_price_history(signal.ticker, start=signal.as_of[:10], end=cutoff.isoformat())
        rows = payload.get("history", {}).get("day", [])
        if isinstance(rows, dict):
            rows = [rows]
        observations = [PriceObservation(date.fromisoformat(row["date"]), float(row["close"])) for row in rows
                        if date.fromisoformat(row["date"]) <= cutoff and is_us_equity_trading_day(date.fromisoformat(row["date"]))]
        outcomes = evaluate_signal_horizons(signal, observations, through_date=cutoff)
        repository.save_outcomes(outcomes)
        results.extend(outcomes)
    return tuple(results)
