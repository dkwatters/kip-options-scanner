# Security Analysis Model Functional Specification

Version: 1.0

Date: 2026-07-06

Status: Current documentation for Security Analysis Model v0.1 behavior.

Terminology note: This file name preserves the historical Technical Analysis Model terminology. The user-facing model name is Security Analysis Model (SAM). Historical TAM references in this document describe the same current SAM behavior unless explicitly used as a protocol identifier such as TAM-001.

---

## Purpose

The Security Analysis Model (SAM), historically called the Technical Analysis Model (TAM), is the platform's independent, security-level technical characterization model. SAM records what was observable about an underlying security at scan time using price history, moving averages, RSI, MACD, realized volatility, and derived state labels.

SAM is observational only. It characterizes the underlying security; it does not recommend trades, predict future price movement, rank option contracts, determine suitability, or change any contract evaluation result.

SAM answers one primary question:

What technical condition was observable for this underlying security at the time of the scan?

---

## Responsibility Boundaries

### SAM vs Research Universe

SAM consumes securities from the selected Research Universe or Research Universe Snapshot for characterization. SAM does not define Research Universe membership, create Research Universe Definitions, run Research Universe Generators, or decide whether a universe is static or dynamic.

Research Universe Snapshots preserve reproducibility for SAM observations by fixing which securities were characterized at observation time.

### SAM vs Opportunity Discovery

Opportunity Discovery observes a Research Universe, retrieves option-chain data, evaluates contracts, and presents visible passing or near-miss candidates. SAM does not select candidates, filter candidates, rank candidates, or decide whether an Opportunity Discovery result passes.

SAM rows may be generated during an Opportunity Discovery run and linked by `scan_id`, but the SAM output remains separate research metadata.

SAM may also run independently through the TAM-001 historical observation protocol. In that mode, SAM collects and persists stock-level technical characterization rows without running Opportunity Discovery.

### SAM vs Option Analysis Model

The Option Analysis Model (OAM), historically called the Contract Quality Model (CQM), evaluates option contracts using contract-level rules and scoring logic. SAM evaluates no option contract fields. It does not use delta, spread, bid, ask, open interest, volume, DTE, strike, or contract quality score.

OAM does not currently consume SAM values.

### SAM vs Evaluation Profiles

Evaluation Profiles identify active analytical configuration and model context. SAM does not currently alter Evaluation Profile behavior, defaults, thresholds, enabled models, output preferences, or profile selection.

### SAM vs Study Protocols

Study Protocols define repeatable observations with purpose, Research Universe, schedule, run mode, and evaluation context. SAM may contribute security-level evidence to scans produced by a Study Protocol, but SAM does not define protocol completion, schedule labels, study validity, or protocol progress.

TAM-001 is the historical protocol identifier for daily SAM technical characterization. It is independent from SP-001 and does not execute option-contract evaluation.

### SAM vs Future Research Universe Generators

Future Research Universe Generators (RUG) may create or refresh Research Universes from selection criteria. SAM does not currently construct universes, admit securities into a universe, remove securities from a universe, or define universe gates.

Future RUG work may study whether SAM states are useful as population-construction features, but that is not implemented in SAM v0.1.

---

## Guiding Principles

- Trend should measure trend only.
- Momentum should measure momentum only.
- Volatility should measure volatility only.
- No SAM field should answer multiple unrelated questions.
- Technical Setup Score is a summary, not a prediction.
- SAM does not rank option contracts.
- SAM does not currently influence Opportunity Discovery behavior.
- SAM does not currently influence Option Analysis Model behavior.
- SAM does not currently influence Evaluation Profile behavior.
- SAM does not currently influence Study Protocol execution.
- SAM output should remain reproducible from observable input data, Research Universe Snapshot membership, and documented decision logic.
- SAM limitations should be documented before expanding indicator coverage or integrating SAM into future RUG behavior.

---

## Inputs

### External Inputs

| Input | Source | Purpose |
| --- | --- | --- |
| Ticker | Research Universe / scan context | Identifies the underlying security. |
| Price history close values | Tradier price history payload | Provides historical close series for indicators. |
| Current quote last price | Tradier quote payload, when available | Used as current price if valid. |
| Scan ID | Opportunity Scan context, optional | Links TAM rows to a scan. |
| Technical timestamp | Scan/runtime context | Records observation time. |
| End date | Scan/runtime context | Bounds the historical price request. |
| Study metadata | TAM-001 / scan context | Identifies TAM-only historical observations. |

### Price Selection

Decision tree:

1. If a valid positive current quote last price is available, use it as `price`.
2. Else, if close history exists, use the last close in the close series as `price`.
3. Else, `price` is unavailable.

Known limitation: moving averages, RSI, MACD, and realized volatility are calculated from historical close values, while `price` may come from the current quote. This means the current price can be fresher than the indicator series.

---

## Output Field Inventory

TAM currently produces persisted repository fields and Explorer-only derived display fields.

### Persisted TAM Fields

| Field | Type | Description |
| --- | --- | --- |
| `ticker` | Text | Uppercase ticker symbol. |
| `scan_id` | Text / null | Optional scan identifier. |
| `technical_timestamp` | Text | Observation timestamp. |
| `price` | Number / null | Current quote last price when available, otherwise latest close. |
| `sma_20` | Number / null | 20-period simple moving average of closes. |
| `sma_50` | Number / null | 50-period simple moving average of closes. |
| `sma_200` | Number / null | 200-period simple moving average of closes. |
| `price_vs_sma_20` | Number / null | Relative price distance from 20 SMA. |
| `price_vs_sma_50` | Number / null | Relative price distance from 50 SMA. |
| `price_vs_sma_200` | Number / null | Relative price distance from 200 SMA. |
| `sma_20_vs_sma_50` | Number / null | Relative 20 SMA distance from 50 SMA. |
| `sma_50_vs_sma_200` | Number / null | Relative 50 SMA distance from 200 SMA. |
| `rsi_14` | Number / null | 14-period RSI. |
| `macd_line` | Number / null | MACD line from 12/26 EMA difference. |
| `macd_signal` | Number / null | 9-period EMA of MACD line. |
| `macd_histogram` | Number / null | MACD line minus signal. |
| `realized_volatility_20d` | Number / null | Annualized 20-day realized volatility. |
| `trend_state` | Text | Persisted trend classification. |
| `momentum_state` | Text | Persisted momentum classification. |
| `volatility_state` | Text | Persisted volatility classification. |
| `technical_score` | Number / null | Reserved persisted field. Currently always null in TAM v0.1 generation. |
| `technical_notes` | Text | Human-readable SMA relationship notes or insufficient-history message. |
| `study_id` | Text / null | Study protocol identifier for TAM rows. |
| `study_name` | Text / null | Study protocol name for TAM rows. |
| `study_version` | Text / null | Study protocol version for TAM rows. |
| `study_purpose` | Text / null | Study protocol purpose for TAM rows. |
| `scheduled_time_label` | Text / null | Scheduled observation label, such as `16:30 ET`. |
| `run_mode` | Text / null | Run mode, such as `research-script` or `scheduled`. |

### Explorer-Derived Display Fields

| Field | Type | Description |
| --- | --- | --- |
| `price_vs_sma_20_state` | Text | Display state derived from `price_vs_sma_20`. |
| `price_vs_sma_50_state` | Text | Display state derived from `price_vs_sma_50`. |
| `price_vs_sma_200_state` | Text | Display state derived from `price_vs_sma_200`. |
| `sma_20_50_state` | Text | Display state derived from `sma_20_vs_sma_50`. |
| `sma_50_200_state` | Text | Display state derived from `sma_50_vs_sma_200`. |
| `macd_state` | Text | Display state derived from MACD line, signal, and histogram. |
| `rsi_regime` | Text | Display regime derived from RSI. |
| `technical_setup_score_experimental` | Number / null | Display-only 0-100 summary score. |
| `technical_setup_grade_experimental` | Text | Display-only grade band for the setup score. |

---

## Base Indicator Calculations

### Simple Moving Averages

Business purpose: Establish short-, medium-, and long-term price reference levels.

Inputs: Historical close values and period length.

Calculation:

`SMA(period) = sum(last period closes) / period`

Decision tree:

1. If fewer than `period` close values are available, output null.
2. Otherwise average the last `period` closes.

Output values:

- `sma_20`: null or numeric value.
- `sma_50`: null or numeric value.
- `sma_200`: null or numeric value.

Worked examples:

- Closes 1 through 20 with period 20: `sma_20 = 10.5`.
- 49 available closes for period 50: `sma_50 = null`.
- Last 20 closes are all 100: `sma_20 = 100`.

Known limitations:

- Uses simple moving averages only.
- Uses close history only.
- Does not adjust classification for market regime, sector behavior, or intraday trend.

Future enhancements:

- Exponential moving averages.
- Multi-timeframe moving-average stacks.
- Slope and persistence measurements.

### Relative Difference Metrics

Business purpose: Normalize price and moving-average relationships as percentage-like ratios.

Inputs: A value and a reference.

Calculation:

`relative_difference = (value - reference) / reference`

Decision tree:

1. If value is null, output null.
2. If reference is null, output null.
3. If reference is zero, output null.
4. Otherwise calculate `(value - reference) / reference`.

Output values:

- `price_vs_sma_20`
- `price_vs_sma_50`
- `price_vs_sma_200`
- `sma_20_vs_sma_50`
- `sma_50_vs_sma_200`

Worked examples:

- Price 105, SMA 100: `(105 - 100) / 100 = 0.05`, meaning 5% above.
- Price 98, SMA 100: `(98 - 100) / 100 = -0.02`, meaning 2% below.
- SMA 20 is 110 and SMA 50 is 100: `0.10`, meaning 20 SMA is 10% above 50 SMA.

Known limitations:

- Distance alone does not measure trend duration.
- Large distances can indicate strength or extension; TAM does not resolve that ambiguity.

Future enhancements:

- Add distance bands.
- Add moving-average slope.
- Add duration above or below reference levels.

### RSI 14

Business purpose: Measure recent price momentum using relative gains and losses.

Inputs: Historical close values and period 14.

Calculation:

TAM uses a Wilder-style RSI calculation:

1. Compute close-to-close changes.
2. Seed average gain and average loss from the first 14 changes.
3. Smooth subsequent gains and losses using:
   `average = ((prior_average * 13) + current_value) / 14`
4. If average loss is zero and average gain is positive, RSI is 100.
5. If average loss is zero and average gain is zero, RSI is 50.
6. Otherwise:
   `RS = average_gain / average_loss`
   `RSI = 100 - (100 / (1 + RS))`

Decision tree:

1. If close count is less than or equal to 14, output null.
2. Calculate smoothed average gain and loss.
3. Apply the zero-loss special cases.
4. Calculate RSI.

Output values:

- `rsi_14`: null or numeric value from 0 to 100.

Worked examples:

- Strictly rising close series with no losses: `rsi_14 = 100`.
- Flat seed and no later movement: `rsi_14 = 50`.
- Average gain 1.5 and average loss 0.5: `RS = 3`, `RSI = 75`.

Known limitations:

- RSI can remain elevated or depressed during strong trends.
- TAM does not use RSI divergence.
- TAM does not compare RSI to sector or market behavior.

Future enhancements:

- RSI slope.
- RSI divergence.
- Multi-period RSI.

### MACD

Business purpose: Measure moving-average momentum using fast and slow exponential moving averages.

Inputs: Historical close values.

Calculation:

- `EMA12`: 12-period exponential moving average.
- `EMA26`: 26-period exponential moving average.
- `macd_line = EMA12 - EMA26`.
- `macd_signal = EMA9(macd_line)`.
- `macd_histogram = macd_line - macd_signal`.

EMA calculation:

1. Multiplier is `2 / (period + 1)`.
2. Before enough values exist for the period, EMA output is null.
3. At the first complete period, seed EMA with the simple average of that period.
4. Thereafter, `EMA = (value - prior_EMA) * multiplier + prior_EMA`.

Decision tree:

1. If fewer than 35 close values are available, output null for all MACD fields.
2. Calculate 12-period and 26-period EMA series.
3. Calculate MACD values where both EMAs are available.
4. Calculate 9-period EMA of MACD values as signal.
5. Use the latest MACD line, signal, and histogram.

Output values:

- `macd_line`
- `macd_signal`
- `macd_histogram`

Worked examples:

- If latest EMA12 is 105 and EMA26 is 100, `macd_line = 5`.
- If `macd_line = 5` and `macd_signal = 3`, `macd_histogram = 2`.
- If only 34 closes exist, all MACD fields are null.

Known limitations:

- MACD is based on close history only.
- TAM does not classify MACD crossovers by recency.
- TAM does not measure histogram acceleration.

Future enhancements:

- Crossover recency.
- Histogram slope.
- MACD zero-line state.

### Realized Volatility 20D

Business purpose: Measure recent annualized realized price variability.

Inputs: Historical close values and period 20.

Calculation:

1. Use the last 20 close-to-close log returns.
2. `log_return = ln(current_close / prior_close)`.
3. `realized_volatility_20d = standard_deviation(log_returns) * sqrt(252)`.

Decision tree:

1. If close count is less than or equal to 20, output null.
2. Build valid positive close-to-close log returns over the last 20 observations.
3. If fewer than two returns remain, output null.
4. Annualize the standard deviation using `sqrt(252)`.

Output values:

- `realized_volatility_20d`: null or numeric annualized volatility.

Worked examples:

- If 20 log returns have standard deviation 0.01, volatility is `0.01 * sqrt(252) = 0.1587`.
- If only 20 closes exist, output is null because the function requires more than 20 closes.
- If the computed value is 0.30, volatility state is moderate.

Known limitations:

- Uses only realized close-to-close volatility.
- Does not use implied volatility.
- Does not use ATR or intraday range.

Future enhancements:

- ATR.
- Volatility percentile.
- Implied versus realized volatility comparison.

---

## Derived Field Specifications

## Trend State

Business purpose: Answer whether the current price and major moving averages are aligned in a bullish, bearish, constructive, deteriorating, mixed, or unavailable trend structure.

Inputs:

- `price`
- `sma_20`
- `sma_50`
- `sma_200`

Mathematical / logical calculation:

Trend state is a strict ordered comparison among price, 20 SMA, 50 SMA, and 200 SMA.

Decision tree:

1. If any input is null, output `insufficient_history`.
2. If `price > sma_20 > sma_50 > sma_200`, output `bullish_alignment`.
3. Else if `price < sma_20 < sma_50 < sma_200`, output `bearish_alignment`.
4. Else if `price > sma_50` and `sma_50 > sma_200`, output `constructive`.
5. Else if `price < sma_50` and `sma_50 < sma_200`, output `deteriorating`.
6. Else output `mixed`.

Output values:

| Stored value | Functional label |
| --- | --- |
| `bullish_alignment` | Strong Bullish |
| `constructive` | Bullish |
| `mixed` | Neutral / Mixed |
| `deteriorating` | Bearish |
| `bearish_alignment` | Strong Bearish |
| `insufficient_history` | Insufficient History |

Worked examples:

| Price | SMA20 | SMA50 | SMA200 | Output | Explanation |
| --- | --- | --- | --- | --- | --- |
| 120 | 115 | 110 | 100 | `bullish_alignment` | Fully stacked bullish order. |
| 112 | 108 | 110 | 100 | `constructive` | Price and 50 SMA are above 200 SMA, but 20/50 are not fully stacked. |
| 95 | 100 | 105 | 110 | `bearish_alignment` | Fully stacked bearish order. |
| 98 | 104 | 100 | 110 | `deteriorating` | Price is below 50 SMA and 50 SMA is below 200 SMA. |
| 105 | 100 | 110 | 102 | `mixed` | No defined trend condition matches. |
| 105 | 100 | 110 | null | `insufficient_history` | 200 SMA is unavailable. |

Known limitations:

- Does not measure slope, duration, volume confirmation, or trend strength.
- Uses fixed 20/50/200 SMA stack only.
- Does not distinguish slight from extreme separation.

Future enhancements:

- ADX for trend strength.
- Moving-average slope.
- Time above or below key averages.
- Multi-timeframe trend state.

## Momentum State

Business purpose: Answer whether RSI and MACD jointly describe positive, negative, overbought, oversold, neutral, or unavailable momentum.

Inputs:

- `rsi_14`
- `macd_line`
- `macd_signal`
- `macd_histogram`

Mathematical / logical calculation:

Momentum state combines RSI thresholds with MACD line/signal and histogram direction.

Decision tree:

1. If any input is null, output `insufficient_history`.
2. If `rsi_14 >= 70`:
   - If `macd_histogram > 0`, output `overbought_positive`.
   - Otherwise output `overbought_mixed`.
3. Else if `rsi_14 <= 30`:
   - If `macd_histogram < 0`, output `oversold_negative`.
   - Otherwise output `oversold_mixed`.
4. Else if `rsi_14 >= 55` and `macd_line > macd_signal` and `macd_histogram > 0`, output `positive`.
5. Else if `rsi_14 <= 45` and `macd_line < macd_signal` and `macd_histogram < 0`, output `negative`.
6. Else output `neutral`.

Output values:

- `overbought_positive`
- `overbought_mixed`
- `oversold_negative`
- `oversold_mixed`
- `positive`
- `negative`
- `neutral`
- `insufficient_history`

Worked examples:

| RSI | MACD Line | Signal | Histogram | Output | Explanation |
| --- | --- | --- | --- | --- | --- |
| 72 | 1.2 | 1.0 | 0.2 | `overbought_positive` | RSI is overbought and histogram is positive. |
| 72 | 0.8 | 1.0 | -0.2 | `overbought_mixed` | RSI is overbought but MACD histogram is not positive. |
| 25 | -1.2 | -1.0 | -0.2 | `oversold_negative` | RSI is oversold and histogram is negative. |
| 25 | -0.8 | -1.0 | 0.2 | `oversold_mixed` | RSI is oversold but histogram is not negative. |
| 60 | 1.2 | 1.0 | 0.2 | `positive` | RSI and MACD both support positive momentum. |
| 40 | 0.8 | 1.0 | -0.2 | `negative` | RSI and MACD both support negative momentum. |
| 50 | 1.2 | 1.0 | 0.2 | `neutral` | RSI is not high enough for positive classification. |
| null | 1.2 | 1.0 | 0.2 | `insufficient_history` | RSI is unavailable. |

Known limitations:

- Combines RSI and MACD into one state, so it is a coarse momentum summary.
- Overbought and oversold labels are descriptive, not signals.
- Does not measure momentum persistence or divergence.

Future enhancements:

- Separate RSI and MACD momentum classifications.
- Momentum slope and acceleration.
- Relative strength versus benchmark or sector.

## Volatility State

Business purpose: Answer whether recent realized volatility is low, moderate, high, or unavailable.

Inputs:

- `realized_volatility_20d`

Mathematical / logical calculation:

Volatility state applies fixed thresholds to annualized 20-day realized volatility.

Decision tree:

1. If `realized_volatility_20d` is null, output `unavailable`.
2. If value is less than 0.25, output `low`.
3. If value is less than or equal to 0.50, output `moderate`.
4. Otherwise output `high`.

Output values:

- `low`
- `moderate`
- `high`
- `unavailable`

Worked examples:

| Realized Volatility | Output | Explanation |
| --- | --- | --- |
| null | `unavailable` | Volatility could not be calculated. |
| 0.20 | `low` | Below 25% annualized. |
| 0.25 | `moderate` | Boundary value belongs to moderate. |
| 0.50 | `moderate` | Boundary value belongs to moderate. |
| 0.51 | `high` | Above 50% annualized. |

Known limitations:

- Fixed thresholds are not ticker-relative.
- Does not compare realized volatility to implied volatility.
- Does not account for earnings events or sector norms.

Future enhancements:

- Volatility percentile by ticker.
- ATR.
- Bollinger Band width.
- Implied versus realized volatility spread.

## RSI Regime

Business purpose: Provide a display-friendly RSI regime independent of the persisted momentum state.

Inputs:

- `rsi_14`

Mathematical / logical calculation:

RSI regime applies fixed thresholds to RSI.

Decision tree:

1. If `rsi_14` is null, output `unavailable`.
2. If `rsi_14 < 40`, output `oversold`.
3. If `rsi_14 <= 70`, output `neutral`.
4. If `rsi_14 <= 80`, output `elevated`.
5. Otherwise output `overbought`.

Output values:

- `oversold`
- `neutral`
- `elevated`
- `overbought`
- `unavailable`

Worked examples:

| RSI | Output |
| --- | --- |
| null | `unavailable` |
| 35 | `oversold` |
| 40 | `neutral` |
| 55 | `neutral` |
| 70 | `neutral` |
| 75 | `elevated` |
| 80 | `elevated` |
| 85 | `overbought` |

Known limitations:

- Display regime thresholds differ from persisted momentum-state RSI thresholds.
- Does not account for trend context.
- Does not imply mean reversion or continuation.

Future enhancements:

- Trend-aware RSI regimes.
- RSI percentile by ticker.
- RSI divergence detection.

## MACD State

Business purpose: Provide a display-friendly MACD direction state independent of the persisted momentum state.

Inputs:

- `macd_line`
- `macd_signal`
- `macd_histogram`

Mathematical / logical calculation:

MACD state checks whether line/signal relationship and histogram sign agree.

Decision tree:

1. If any input is null, output `unavailable`.
2. If `macd_line > macd_signal` and `macd_histogram > 0`, output `bullish`.
3. If `macd_line < macd_signal` and `macd_histogram < 0`, output `bearish`.
4. Otherwise output `neutral`.

Output values:

- `bullish`
- `bearish`
- `neutral`
- `unavailable`

Worked examples:

| MACD Line | Signal | Histogram | Output |
| --- | --- | --- | --- |
| 1.2 | 0.9 | 0.3 | `bullish` |
| 0.9 | 1.2 | -0.3 | `bearish` |
| 1.2 | 0.9 | -0.1 | `neutral` |
| 1.0 | 1.0 | 0.0 | `neutral` |
| null | 0.9 | 0.3 | `unavailable` |

Known limitations:

- Does not measure crossover age.
- Does not consider whether MACD is above or below zero.
- Requires agreement between line/signal and histogram sign.

Future enhancements:

- Zero-line classification.
- Crossover recency.
- Histogram slope.

## Price vs SMA20

Business purpose: Show whether current price is above, below, or near the short-term moving average.

Inputs:

- `price_vs_sma_20`

Mathematical / logical calculation:

The raw metric is `(price - sma_20) / sma_20`. The display state uses a near threshold of 1%.

Decision tree:

1. If `price_vs_sma_20` is null, output `unavailable`.
2. If `abs(price_vs_sma_20) <= 0.01`, output `near`.
3. If `price_vs_sma_20 > 0`, output `above`.
4. Otherwise output `below`.

Output values:

- Raw: null or numeric relative difference.
- State: `above`, `below`, `near`, `unavailable`.

Worked examples:

| Price | SMA20 | Raw | State |
| --- | --- | --- | --- |
| 102 | 100 | 0.02 | `above` |
| 98 | 100 | -0.02 | `below` |
| 100.5 | 100 | 0.005 | `near` |
| 99 | 100 | -0.01 | `near` |

Known limitations:

- Near threshold is fixed at 1%.
- State does not indicate duration above or below SMA20.

Future enhancements:

- Ticker-relative thresholds.
- Slope and persistence.

## Price vs SMA50

Business purpose: Show whether current price is above, below, or near the medium-term moving average.

Inputs:

- `price_vs_sma_50`

Mathematical / logical calculation:

The raw metric is `(price - sma_50) / sma_50`. The display state uses a near threshold of 1%.

Decision tree:

1. If `price_vs_sma_50` is null, output `unavailable`.
2. If `abs(price_vs_sma_50) <= 0.01`, output `near`.
3. If `price_vs_sma_50 > 0`, output `above`.
4. Otherwise output `below`.

Output values:

- Raw: null or numeric relative difference.
- State: `above`, `below`, `near`, `unavailable`.

Worked examples:

| Price | SMA50 | Raw | State |
| --- | --- | --- | --- |
| 106 | 100 | 0.06 | `above` |
| 94 | 100 | -0.06 | `below` |
| 101 | 100 | 0.01 | `near` |
| 100 | 100 | 0.00 | `near` |

Known limitations:

- Does not distinguish a decisive break from a sustained trend.
- Near threshold is fixed.

Future enhancements:

- Distance bands.
- Retest and breakout classification.

## Price vs SMA200

Business purpose: Show whether current price is above, below, or near the long-term moving average.

Inputs:

- `price_vs_sma_200`

Mathematical / logical calculation:

The raw metric is `(price - sma_200) / sma_200`. The display state uses a near threshold of 1%.

Decision tree:

1. If `price_vs_sma_200` is null, output `unavailable`.
2. If `abs(price_vs_sma_200) <= 0.01`, output `near`.
3. If `price_vs_sma_200 > 0`, output `above`.
4. Otherwise output `below`.

Output values:

- Raw: null or numeric relative difference.
- State: `above`, `below`, `near`, `unavailable`.

Worked examples:

| Price | SMA200 | Raw | State |
| --- | --- | --- | --- |
| 112 | 100 | 0.12 | `above` |
| 96 | 100 | -0.04 | `below` |
| 100.5 | 100 | 0.005 | `near` |
| null | 100 | null | `unavailable` |

Known limitations:

- Requires at least 200 historical closes for the SMA.
- Does not measure long-term trend slope.

Future enhancements:

- 200 SMA slope.
- Duration above or below 200 SMA.

## SMA20 vs SMA50

Business purpose: Show whether the short-term moving average is above or below the medium-term moving average.

Inputs:

- `sma_20_vs_sma_50`

Mathematical / logical calculation:

The raw metric is `(sma_20 - sma_50) / sma_50`.

Decision tree:

1. If `sma_20_vs_sma_50` is null, output `unavailable`.
2. If `sma_20_vs_sma_50 > 0`, output `bullish`.
3. Otherwise output `bearish`.

Output values:

- Raw: null or numeric relative difference.
- State: `bullish`, `bearish`, `unavailable`.

Worked examples:

| SMA20 | SMA50 | Raw | State |
| --- | --- | --- | --- |
| 104 | 100 | 0.04 | `bullish` |
| 96 | 100 | -0.04 | `bearish` |
| 100 | 100 | 0.00 | `bearish` |
| null | 100 | null | `unavailable` |

Known limitations:

- Equality is classified as bearish because only values greater than zero are bullish.
- Does not distinguish recent crossovers from old alignments.

Future enhancements:

- Add neutral/flat state for near-zero relationships.
- Track crossover recency.

## SMA50 vs SMA200

Business purpose: Show whether the medium-term moving average is above or below the long-term moving average.

Inputs:

- `sma_50_vs_sma_200`

Mathematical / logical calculation:

The raw metric is `(sma_50 - sma_200) / sma_200`.

Decision tree:

1. If `sma_50_vs_sma_200` is null, output `unavailable`.
2. If `sma_50_vs_sma_200 > 0`, output `bullish`.
3. Otherwise output `bearish`.

Output values:

- Raw: null or numeric relative difference.
- State: `bullish`, `bearish`, `unavailable`.

Worked examples:

| SMA50 | SMA200 | Raw | State |
| --- | --- | --- | --- |
| 108 | 100 | 0.08 | `bullish` |
| 98 | 100 | -0.02 | `bearish` |
| 100 | 100 | 0.00 | `bearish` |
| 100 | null | null | `unavailable` |

Known limitations:

- Equality is classified as bearish because only values greater than zero are bullish.
- Does not measure trend strength.

Future enhancements:

- Neutral band around zero.
- Golden-cross/death-cross timing.

## Technical Setup Score

Business purpose: Provide a display-only, Experimental / Observational 0-100 summary of selected SAM states for faster visual review in the Security Analysis Explorer.

Inputs:

- `price_vs_sma_20`
- `price_vs_sma_50`
- `price_vs_sma_200`
- `sma_20_vs_sma_50`
- `sma_50_vs_sma_200`
- `macd_line`
- `macd_signal`
- `macd_histogram`
- `rsi_14`
- `volatility_state`

Mathematical / logical calculation:

The score is additive and capped to the range 0 through 100. It is rounded to one decimal place.

Availability decision tree:

1. Derive display fields for trend checks, MACD, and RSI.
2. `has_trend_data` is true if any of the five trend display fields is not `unavailable`.
3. `has_macd_data` is true if any MACD numeric field is present.
4. `has_rsi_data` is true if RSI is present.
5. `has_volatility_data` is true if volatility state is not empty, `unavailable`, or `insufficient_history`.
6. If none of those data groups is available, output null.

Scoring decision tree:

1. Start score at 0.
2. Trend contribution: add 8 points for each true condition:
   - `price_vs_sma_20_state == above`
   - `price_vs_sma_50_state == above`
   - `price_vs_sma_200_state == above`
   - `sma_20_50_state == bullish`
   - `sma_50_200_state == bullish`
3. MACD contribution:
   - Add 12.5 points if `macd_line > macd_signal`.
   - Add 12.5 points if `macd_histogram > 0`.
4. RSI contribution:
   - Add 20 points if `50 <= rsi_14 <= 70`.
   - Add 10 points if `40 <= rsi_14 < 50` or `70 < rsi_14 <= 80`.
   - Add 5 points for all other available RSI values.
5. Volatility contribution:
   - Add 15 points if volatility state is `moderate`, `normal`, or `neutral`.
   - Add 10 points if volatility state is `low`.
   - Add 5 points if volatility state is `high`.
6. Clamp to 0-100.
7. Round to one decimal place.

Output values:

- Null when no scoring inputs are available.
- Numeric score from 0.0 to 100.0.

Worked examples:

Example 1: Full constructive setup.

Inputs:

- Price above 20/50/200 SMAs: 3 checks = 24 points.
- 20 SMA above 50 SMA and 50 SMA above 200 SMA: 2 checks = 16 points.
- MACD line above signal and histogram positive: 25 points.
- RSI 62: 20 points.
- Volatility moderate: 15 points.

Score: `24 + 16 + 25 + 20 + 15 = 100.0`.

Example 2: Partial setup.

Inputs:

- Price above 20 SMA only: 8 points.
- 50 SMA above 200 SMA: 8 points.
- MACD line below signal and histogram negative: 0 points.
- RSI 75: 10 points.
- Volatility high: 5 points.

Score: `8 + 8 + 0 + 10 + 5 = 31.0`.

Example 3: No available inputs.

Inputs:

- All trend fields null.
- All MACD fields null.
- RSI null.
- Volatility state unavailable.

Score: null.

Known limitations:

- The score is descriptive, unvalidated, and display-only.
- It is not a prediction.
- It does not rank option contracts.
- It does not define Research Universe gates.
- It does not influence Opportunity Discovery, OAM, OAE, rankings, filters, thresholds, Evaluation Profiles, or Study Protocols.
- Missing groups reduce possible point contribution but do not rescale available groups.

Future enhancements:

- Validate score behavior against longitudinal evidence.
- Add component-level display.
- Consider ticker-relative volatility and relative strength.
- Consider whether separate scores are needed for calls, puts, or neutral strategies before any future evaluated-model promotion.

## Technical Setup Grade

Business purpose: Convert the display-only Technical Setup Score into a compact label for review.

Inputs:

- `technical_setup_score_experimental`

Mathematical / logical calculation:

Decision tree:

1. If score is null, output `Unavailable`.
2. If score is greater than or equal to 80, output `Strong technical setup`.
3. If score is greater than or equal to 65, output `Constructive`.
4. If score is greater than or equal to 45, output `Neutral / mixed`.
5. If score is greater than or equal to 25, output `Weak`.
6. Otherwise output `Poor`.

Output values:

- `Strong technical setup`
- `Constructive`
- `Neutral / mixed`
- `Weak`
- `Poor`
- `Unavailable`

Worked examples:

| Score | Grade |
| --- | --- |
| null | `Unavailable` |
| 100 | `Strong technical setup` |
| 80 | `Strong technical setup` |
| 79 | `Constructive` |
| 65 | `Constructive` |
| 64 | `Neutral / mixed` |
| 45 | `Neutral / mixed` |
| 44 | `Weak` |
| 25 | `Weak` |
| 24 | `Poor` |
| 0 | `Poor` |

Known limitations:

- Grade bands are descriptive and unvalidated.
- Grade does not imply trade quality or future outcome.

Future enhancements:

- Evidence-backed calibration.
- Separate grade display by strategy context if TAM is ever promoted beyond observational use.

## Technical Score

Business purpose: Reserve a persisted numeric TAM score field for possible future model output while preserving the current repository shape.

Inputs:

- None in current TAM v0.1 generation.

Mathematical / logical calculation:

No calculation is currently performed.

Decision tree:

1. During current TAM row generation, always output null.

Output values:

- `technical_score = null`

Worked examples:

- A fully characterized row with price, SMA, RSI, MACD, and volatility still stores `technical_score = null`.
- An insufficient-history row also stores `technical_score = null`.

Known limitations:

- This field is not the Technical Setup Score.
- This field is persisted, while Technical Setup Score is currently derived for Explorer display.
- Consumers should not interpret null as a weak, neutral, or failed technical condition.

Future enhancements:

- A future TAM version may either define this field formally or continue using display-only setup scoring.
- Any future persisted score would require separate model-version documentation and validation.

## Technical Notes

Business purpose: Preserve a compact human-readable summary of available moving-average relationship distances.

Inputs:

- `price_vs_sma_20`
- `price_vs_sma_50`
- `price_vs_sma_200`
- `sma_20_vs_sma_50`
- `sma_50_vs_sma_200`

Mathematical / logical calculation:

For each available relationship:

1. Direction is `above` if the relative value is greater than or equal to 0.
2. Direction is `below` if the relative value is less than 0.
3. Absolute distance is formatted as a percentage with two decimal places.
4. Relationship notes are joined with `; `.

If no relationship notes are available, TAM outputs:

`Insufficient price history for full TAM characterization.`

Decision tree:

1. For each relationship, skip null values.
2. Format non-null values as `{label}: {absolute percent} {above|below}`.
3. Join formatted notes.
4. If the result is empty, use the insufficient-history message.

Output values:

- Human-readable relationship summary string.
- Insufficient-history message.

Worked examples:

- `price_vs_sma_20 = 0.02` produces `price vs 20 SMA: 2.00% above`.
- `price_vs_sma_50 = -0.03` produces `price vs 50 SMA: 3.00% below`.
- `sma_20_vs_sma_50 = 0.00` produces `20/50 SMA: 0.00% above`.
- All relationship values null produces `Insufficient price history for full TAM characterization.`

Known limitations:

- Technical notes summarize only moving-average relationships.
- Notes do not include RSI, MACD, volatility, trend state, momentum state, or score.

Future enhancements:

- Structured note components.
- Include missing-indicator details.
- Include indicator-specific warnings without changing model behavior.

---

## Assumptions

- Historical close values are ordered oldest to newest by the data provider payload.
- Only positive close values are retained from history payloads.
- Current quote price is used only when it is a valid positive number.
- Indicator calculations are based on available close history and do not impute missing values.
- Null indicator values are expected when history is insufficient.
- Display-derived fields in the Security Analysis Explorer are presentation-time calculations and are not persisted by SAM v0.1 generation.

---

## TAM-001 Historical Observation Protocol

Study metadata:

| Field | Value |
| --- | --- |
| `study_id` | `TAM-001` |
| `study_name` | `Daily Technical Characterization` |
| `study_version` | `v0.1` |
| `study_purpose` | `Collect daily stock-level technical observations.` |
| Suggested schedule | Once daily after market close, `16:30 ET` |
| Research Universe | `data/technology_growth_ai_v1.csv` |

Execution boundary:

- Runner: `technical_scan.py`.
- Loads the active Technology Growth AI Research Universe.
- Fetches price history and quotes required for SAM.
- Persists rows to `technical_characterization`.
- Does not fetch option expirations.
- Does not fetch option chains.
- Does not run OAM.
- Does not create evaluated contract rows.
- Does not create rule evaluation rows.
- Does not alter OD, OAE, Evaluation Profile, ranking, or threshold behavior.

Scheduling behavior:

1. Scheduled runs use `run_mode = scheduled`.
2. Scheduled runs require a schedule label, normally `16:30 ET`.
3. Scheduled runs check `market_calendar` before collecting data.
4. Weekends and U.S. equity market holidays are skipped.
5. Manual validation can bypass the calendar with the runner's non-trading-day override.

Cloud execution:

`technical_scan.py` supports cloud execution through environment variables:

- `CLOUD_RUNNER`
- `TAM_RUN_MODE` or `RESEARCH_RUN_MODE`
- `TAM_SCHEDULED_TIME_LABEL`, `SCHEDULED_TIME_LABEL`, or `RESEARCH_SCHEDULED_TIME_LABEL`
- `RESEARCH_REPOSITORY_BACKEND`
- `DATABASE_URL`
- `TRADIER_API_TOKEN`
- `TRADIER_ENVIRONMENT`

Persistence:

TAM-only rows are persisted directly to `technical_characterization`. They are queryable by:

- `ticker`
- `technical_timestamp`
- `study_id`
- `run_mode`
- `scheduled_time_label`

Schema note:

TAM-001 requires nullable study metadata columns on `technical_characterization`: `study_id`, `study_name`, `study_version`, `study_purpose`, `scheduled_time_label`, and `run_mode`. Existing rows remain valid with null metadata.

---

## Current Limitations

- TAM v0.1 is security-level only and does not understand option strategy direction.
- TAM-001 captures historical technical observations only; it does not produce contract-quality evidence.
- The Technical Setup Score is unvalidated and display-only.
- Moving-average relationships do not include slope, duration, or crossover age.
- Volatility uses realized close-to-close volatility only.
- RSI and MACD are calculated from close history only.
- No sector-relative, market-relative, or benchmark-relative comparisons are currently produced.
- No market regime classifier is currently produced.
- No forward outcome attribution is currently produced.
- No TAM field currently changes application behavior outside TAM display and repository observation.

---

## Future Evolution

Future TAM work may expand technical characterization without changing current behavior unless explicitly implemented in a later model version.

Potential additions:

- Additional technical indicators.
- Relative strength against a benchmark.
- Sector-relative momentum.
- ATR.
- Bollinger Bands.
- ADX.
- Moving-average slope and crossover recency.
- Multi-timeframe analysis.
- Market regime classification.
- Volatility percentiles.
- Momentum persistence and divergence measures.
- TAM component scoring transparency.
- Integration into future Research Universe Generators (RUG) as optional population-construction evidence.

Any future integration into RUG, Opportunity Discovery, OAM, Evaluation Profiles, Study Protocols, or scoring behavior should be treated as a separate research and implementation decision. Such integration is not part of SAM v0.1 and is not implemented by this specification.

---

## Validation Scope

This specification documents current behavior only.

Validation expectations for this documentation sprint:

- No executable code changes.
- No database schema changes.
- No UI behavior changes.
- No scoring logic changes.
- No Opportunity Discovery changes.
- No OAM changes.
- No Evaluation Profile changes.
- No Study Protocol changes.
- No Research Repository behavior changes.
- No cloud infrastructure changes.
