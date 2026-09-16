"""Paired forecast errors against existing, verified volatility Outcomes."""
from math import isfinite, sqrt
from statistics import mean, median
from src.garch_challenger import MODEL_ID, MODEL_VERSION, HORIZONS
from src.signals import SignalFamily
from src.signal_outcomes import OutcomeFamily, OutcomeStatus


def forecast_scorecard(signals, outcomes):
    selected = {s.signal_id: s for s in signals if s.model_id == MODEL_ID and s.model_version == MODEL_VERSION
                and s.signal_family is SignalFamily.VOLATILITY}
    by_key = {(o.signal_id, o.horizon_trading_days): o for o in outcomes if o.signal_id in selected
              and o.outcome_family is OutcomeFamily.VOLATILITY}
    results, errors = {}, []
    for horizon in HORIZONS:
        rows = []
        for signal in selected.values():
            outcome = by_key.get((signal.signal_id, horizon))
            if outcome is None or outcome.status is not OutcomeStatus.EVALUATED:
                continue
            values = (signal.components.get(f"forecast_volatility_{horizon}d"),
                      signal.components.get("realized_volatility_20d"), outcome.components.get("realized_volatility"))
            if any(not isinstance(v, (int,float)) or not isfinite(v) or v < 0 for v in values):
                continue
            forecast, baseline, actual = values
            row = {"signal_id": signal.signal_id, "ticker": signal.ticker, "horizon": horizon,
                   "forecast": forecast, "baseline": baseline, "actual": actual,
                   "error": forecast-actual, "absolute_error": abs(forecast-actual), "squared_error": (forecast-actual)**2,
                   "baseline_error": baseline-actual, "baseline_absolute_error": abs(baseline-actual),
                   "baseline_squared_error": (baseline-actual)**2}
            rows.append(row)
        metrics = {"sample_count": len(rows), "signal_count": len(selected),
                   "coverage": len(rows)/len(selected) if selected else 0,
                   "sample_label": "preliminary (<30 paired observations)" if len(rows) < 30 else "descriptive; no significance test"}
        for prefix in ("", "baseline_"):
            metrics[prefix+"mae"] = mean(r[prefix+"absolute_error"] for r in rows) if rows else None
            metrics[prefix+"rmse"] = sqrt(mean(r[prefix+"squared_error"] for r in rows)) if rows else None
            metrics[prefix+"bias"] = mean(r[prefix+"error"] for r in rows) if rows else None
            metrics[prefix+"median_absolute_error"] = median(r[prefix+"absolute_error"] for r in rows) if rows else None
        metrics["mae_difference"] = metrics["mae"]-metrics["baseline_mae"] if rows else None
        # Absolute differences avoid unstable relative percentages near zero.
        results[horizon] = metrics
        errors.extend(rows)
    return {"horizons": results, "errors": errors}
