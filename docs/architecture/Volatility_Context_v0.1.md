# Volatility Context v0.1

## Purpose

Volatility Context is a deterministic, non-directional description of a security's current dispersion environment. It answers whether volatility is quiet, normal, elevated, or extreme relative to the security's own recent history and whether recent volatility is expanding, stable, or contracting. It does not predict price direction and does not change Technical Setup or options scoring.

Future GARCH-family forecasts must demonstrate value relative to this simpler deterministic volatility context rather than merely producing sophisticated-looking outputs.

## Calculations and lookbacks

- Realized volatility uses the sample standard deviation of completed daily log returns over 10 and 20 return observations, annualized by `sqrt(252)`. Annualized volatility is dispersion, not probability.
- ATR% is the arithmetic mean of 14 true ranges divided by the latest completed-bar close. True range includes overnight gaps.
- Bollinger Bandwidth uses 20 closes and population standard deviation: `(upper - lower) / middle`, with bands at two standard deviations.
- The volatility percentile is the empirical percentage of rolling 20-day realized-volatility observations less than or equal to the current observation. It uses at most the latest 252 observations and requires at least 60. The current observation is included.

The existing TAM history request begins 320 calendar days before analysis and is deliberately unchanged so Technical Setup inputs and semantics remain stable. The percentile uses all available rolling observations up to its 252-observation cap; actual availability is preserved in metadata.

## Regime and trend definitions

`rolling-vol-percentile-v0.1` defines: quiet below 25; normal from 25 through below 70; elevated from 70 through below 90; extreme at 90 or above. These thresholds are fixed for v0.1 and were not optimized against Outcomes.

`rv10-to-rv20-ratio-v0.1` defines: expanding when RV10/RV20 is greater than 1.10; contracting below 0.90; stable inclusively from 0.90 through 1.10. This is deliberately transparent and is not a weighted score.

## Point-in-time policy

The existing Technical Setup cutoff and quote behavior remain unchanged. Volatility Context has a separate conservative completed-daily-bar boundary because provider daily history does not carry a trustworthy bar-completion timestamp. For every analysis date, live or replayed, the eligible boundary is the most recent U.S. equity trading session strictly before the analysis calendar date. The analysis-date OHLC row is therefore excluded even after the close. On weekends and supported full-day market holidays, the boundary walks backward to the latest eligible session. Non-session OHLC rows are rejected independently of the provider response.

Historical replay never requests a live quote and cannot use a bar on or after its historical analysis date. Live quotes may still support the unchanged Technical Setup observation, but are never inputs to Volatility Context. Input bars are dated, sorted, deduplicated, session-validated, and filtered at the volatility boundary. Percentiles, normalization, regime, and trend use only that filtered prefix. No full-sample or future-derived thresholds are used.

## Insufficient data

A useful partial volatility-family Signal is emitted when valid completed OHLC bars exist. Unavailable calculations remain null; percentile and regime are not fabricated. Metadata uses `data_quality=partial_history`, `insufficient_history=true`, and records observation counts. If no valid OHLC bars exist, the shared boundary retains the Technical Setup Signal and does not emit Volatility Context.

## Signal structure

The immutable model identity is `volatility-context · volatility-context-v0.1`. The Signal uses `signal_family=volatility`, `direction=not_applicable`, `conviction=0`, and `confidence=null`. Components contain `realized_volatility_10d`, `realized_volatility_20d`, `atr_pct_14d`, `bollinger_bandwidth_20d`, and `volatility_percentile`. Metadata contains regime, trend, versioned definitions, history bounds, counts, data quality, insufficient-history status, annualization factor, and source scan ID. Identity is deterministic from model/version, ticker, as-of, and source scan.

## Volatility Outcomes

The existing 5/20/60-session evaluator now routes volatility-family Signals to annualized subsequent realized volatility. The convention is 5 log returns from 6 closes, 20 log returns from 21 closes, and 60 log returns from 61 closes: one starting-session close plus the stated number of subsequent verified session closes. Weekends and exchange holidays are excluded, while a missing interior session produces `missing_data`. Immature horizons produce `not_yet_eligible`. Components preserve return-observation count, annualization factor, starting regime, and a descriptive comparison to starting RV20: increased above 1.10x, decreased below 0.90x, otherwise broadly consistent. Directional correctness and return accuracy are never populated.

## Model Lab and evaluation

Model Lab shows the model/version, security, as-of, N/A direction, regime, trend, percentile, both realized-volatility measures, ATR%, Bollinger Bandwidth, and data quality. Volatility scorecards show counts, regime/trend distributions, Outcome coverage, and average/median subsequent realized volatility overall and by starting regime, always with sample counts. They contain no directional tiles or hit rate.

## Known limitations and deferred models

Close-to-close realized volatility misses intraday paths; ATR is a descriptive range statistic; the empirical percentile is coarse with limited history; corporate-action quality depends on provider history; and no formal forecast target or accuracy statistic exists. ARCH, GARCH, EGARCH, GJR-GARCH, regime switching, stochastic volatility, implied-versus-realized comparisons, options integration, optimization, and promotion are deferred. Later forecast models must be evaluated out of sample against this frozen deterministic baseline using the same verified-session Outcomes.
