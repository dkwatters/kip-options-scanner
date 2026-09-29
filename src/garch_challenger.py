"""Experimental GARCH(1,1); no quotes, fitting on future data, or fallback forecasts."""
from dataclasses import dataclass
from datetime import date, timedelta
from hashlib import sha256
from importlib.metadata import version
import json
from math import isfinite, log, sqrt
from statistics import stdev
from typing import Any
from uuid import NAMESPACE_URL, uuid5
import warnings

from src.market_calendar import is_us_equity_trading_day
from src.technical_analysis import most_recent_completed_trading_session
from src.signals import Signal, SignalDirection, SignalFamily

MODEL_ID = "garch-volatility"
MODEL_VERSION = "garch-1-1-v0.1"
HORIZONS = (5, 20, 60)
MIN_RETURNS = 252
PREFERRED_RETURNS = 500
HISTORY_CALENDAR_DAYS = 800
PERSISTENCE_LIMIT = 0.995


@dataclass(frozen=True)
class GarchResult:
    signal: Signal | None
    status: str
    diagnostics: dict[str, Any]


def signal_identity(ticker: str, as_of: date) -> str:
    return str(uuid5(NAMESPACE_URL, f"{MODEL_ID}|{MODEL_VERSION}|{ticker.strip().upper()}|{as_of.isoformat()}"))


def completed_closes(payload: dict, as_of: date):
    """Strict contiguous session history, ending at the established completed-bar cutoff."""
    cutoff = most_recent_completed_trading_session(as_of)
    rows = payload.get("history", {}).get("day", [])
    if isinstance(rows, dict):
        rows = [rows]
    if not isinstance(rows, list):
        raise ValueError("History must contain daily observations")
    prices = {}
    for row in rows:
        day = date.fromisoformat(str(row["date"]))
        if day > cutoff or not is_us_equity_trading_day(day):
            continue
        close = float(row["close"])
        if day in prices or not isfinite(close) or close <= 0:
            raise ValueError("Duplicate session or invalid completed close")
        prices[day] = close
    selected = sorted(prices.items())[-(PREFERRED_RETURNS + 1):]
    if selected:
        if selected[-1][0] != cutoff:
            raise ValueError("History does not end at the latest completed session")
        cursor = selected[0][0]
        while cursor <= cutoff:
            if is_us_equity_trading_day(cursor) and cursor not in prices:
                raise ValueError(f"Missing training session {cursor}")
            cursor += timedelta(days=1)
    return selected


def _fit(percent_returns):
    from arch import arch_model
    return arch_model(percent_returns, mean="Zero", vol="GARCH", p=1, o=0, q=1,
                      power=2.0, dist="normal", rescale=False).fit(
        disp="off", update_freq=0, show_warning=False, tol=1e-8,
        options={"maxiter": 1000},
    )


def aggregate_forecasts(variance_path):
    """Root expected annualized sample variance for existing Outcome windows.

    Training ends at t. Outcome starts at t+1 close, so its H returns are
    steps 2..H+1. Zero-mean GARCH returns are uncorrelated: E[sample variance]
    equals the mean conditional variances. This is NOT E[sample volatility].
    Library variances use percent-return squared units.
    """
    path = tuple(float(v) for v in variance_path)
    if len(path) < max(HORIZONS) + 1 or any(not isfinite(v) or v <= 0 for v in path):
        raise ValueError("Invalid analytic variance forecast")
    return {f"forecast_volatility_{h}d": sqrt(252 * sum(path[1:h+1]) / h) / 100 for h in HORIZONS}


def fit_garch(ticker: str, as_of: date, payload: dict, *, source: str = "tradier-daily-history") -> GarchResult:
    ticker = ticker.strip().upper()
    diagnostics = {"model_id": MODEL_ID, "model_version": MODEL_VERSION,
                   "analysis_date": as_of.isoformat(), "source": source}
    if not ticker:
        return GarchResult(None, "provider_history_failure", {**diagnostics, "error": "Ticker required"})
    try:
        rows = completed_closes(payload, as_of)
    except (ValueError, KeyError, TypeError, AttributeError) as error:
        return GarchResult(None, "provider_history_failure", {**diagnostics, "error": str(error)})
    # Log differences avoid overflow/underflow for finite positive provider prices.
    returns = [100 * (log(rows[i][1]) - log(rows[i-1][1])) for i in range(1, len(rows))]
    diagnostics.update({"observation_count": len(returns), "training_start": rows[0][0].isoformat() if rows else None,
                        "training_end": rows[-1][0].isoformat() if rows else None})
    if len(returns) < MIN_RETURNS:
        return GarchResult(None, "insufficient_history", diagnostics)
    if not all(isfinite(r) for r in returns) or stdev(returns) < 1e-8:
        return GarchResult(None, "numerical_failure", {**diagnostics, "error": "Degenerate return series"})
    try:
        diagnostics.update({"library": "arch", "library_version": version("arch"),
                            "numpy_version": version("numpy"), "scipy_version": version("scipy")})
    except Exception as error:
        return GarchResult(None, "dependency_failure", {**diagnostics, "error": str(error)})
    diagnostics["history_sha256"] = sha256(json.dumps([(d.isoformat(), c) for d,c in rows], separators=(",", ":")).encode()).hexdigest()
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            fit = _fit(returns)
        diagnostics.update({"convergence_flag": int(fit.convergence_flag),
                            "optimizer_message": str(fit.optimization_result.message),
                            "optimizer_iterations": int(fit.optimization_result.nit),
                            "warnings": [str(w.message) for w in caught]})
    except Exception as error:
        return GarchResult(None, "optimizer_failure", {**diagnostics, "error": str(error)})
    if fit.convergence_flag != 0:
        return GarchResult(None, "non_convergence", diagnostics)
    try:
        omega, alpha, beta = (float(fit.params[name]) for name in ("omega", "alpha[1]", "beta[1]"))
        persistence = alpha + beta
        diagnostics["fitted_parameters"] = {"omega": omega, "alpha": alpha, "beta": beta, "persistence": persistence}
        if not all(isfinite(x) for x in (omega, alpha, beta)) or omega <= 0 or min(alpha, beta) < 0:
            return GarchResult(None, "invalid_parameters", diagnostics)
        if persistence >= PERSISTENCE_LIMIT:
            return GarchResult(None, "nonstationary_or_near_boundary", diagnostics)
        forecasts = aggregate_forecasts(fit.forecast(horizon=61, method="analytic", reindex=False).variance.values[-1])
        current = float(fit.conditional_volatility[-1]) * sqrt(252) / 100
        if not isfinite(current) or current <= 0:
            raise ValueError("Invalid conditional volatility")
        rv20 = stdev(returns[-20:]) * sqrt(252) / 100
        rv10 = stdev(returns[-10:]) * sqrt(252) / 100
        components = {**forecasts, "current_conditional_volatility": current,
                      "omega": omega, "alpha": alpha, "beta": beta, "persistence": persistence,
                      "realized_volatility_20d": rv20, "realized_volatility_10d": rv10}
    except Exception as error:
        return GarchResult(None, "numerical_failure", {**diagnostics, "error": str(error)})
    metadata = {**diagnostics, "status": "valid", "data_quality": "sufficient_history",
                "experimental": True, "source_scan_id": f"garch-explicit:{ticker}:{as_of}",
                "return_convention": "100 * log(close / prior_close)", "annualization_factor": 252,
                "parameter_units": "omega: percent-return squared; alpha/beta: dimensionless",
                "model_specification": "zero-mean Gaussian GARCH(1,1), power=2, rescale=False",
                "forecast_convention": "sqrt(252 * mean(variance steps 2..H+1)) / 100",
                "target": "root expected sample variance, not expected sample standard deviation",
                "baseline": "frozen trailing RV20, sample stdev, annualized sqrt(252)",
                "history_request_calendar_days": HISTORY_CALENDAR_DAYS,
                "history_request_start": (as_of - timedelta(days=HISTORY_CALENDAR_DAYS)).isoformat(),
                "history_request_end": most_recent_completed_trading_session(as_of).isoformat(),
                "minimum_returns": MIN_RETURNS, "preferred_returns": PREFERRED_RETURNS,
                "persistence_rejection_threshold": PERSISTENCE_LIMIT,
                "price_adjustments": "provider supplied; revisions/corporate actions not reconstructed"}
    signal = Signal(signal_identity(ticker, as_of), ticker, as_of.isoformat(), MODEL_ID, MODEL_VERSION,
                    SignalDirection.NOT_APPLICABLE, 0.0, "Experimental variance forecast; compare out-of-sample errors with frozen RV20.",
                    components=components, metadata=metadata, evidence_refs=(f"{source}:{metadata['history_sha256']}",),
                    created_at=as_of.isoformat(), signal_family=SignalFamily.VOLATILITY)
    return GarchResult(signal, "valid", metadata)
