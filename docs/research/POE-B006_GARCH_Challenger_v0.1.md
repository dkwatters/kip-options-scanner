# POE-B006 — GARCH Challenger v0.1

Status: implemented experimental research challenger; product-owner manual acceptance = **PASS**.
Synthetic developer evidence and single-security live acceptance establish implementation behavior. Neither is authoritative RCE evidence or a claim of forecast value, market superiority, predictive edge, profitability, or statistical significance.

## Recovery (2026-09-15)

Recovered branch `feature/garch-challenger-v0.1` at accepted baseline
`25c88047c4394e8e5659326d370fdfc964c46893`. The four modified files were CI,
`.gitignore`, requirements, and Model Lab. Six untracked files contained the
fitter, evaluator, service, UI, synthetic seeder, and 33 GARCH tests. All were
inspected and preserved; no reset, cleanup, replacement checkout, or worktree
recreation occurred.

- COMPLETE in recovered draft: model specification, parameter/forecast persistence,
  deterministic identity, paired error metrics, explicit run/retry path, Model Lab,
  synthetic fixture, CI path additions, core tests.
- PARTIAL: validation, defensive failure handling, completed-session refresh guard,
  and documentation of statistical and operational limitations.
- NOT STARTED: this POE and a recorded final validation/acceptance procedure.
- INTERRUPTION DAMAGE: no truncated files or partial syntax edits found. Initial
  compilation passed. A first test run accidentally used the shared root environment
  without arch (13 failed, 14 passed, 6 errors); the recovered worktree `.venv`
  contained arch and passed all original 33 tests. No install was necessary.

Recovery completion adds dependency-failure handling, numerically safe log differences,
a completed-session cap on Outcome refresh, three boundary tests, and explicit UI
coverage caveats. Uncommitted code was reviewed rather than presumed accepted.

## Product question and architecture

Does a simple GARCH forecast add measurable out-of-sample information beyond
Volatility Context's RV20/persistence baseline? No superiority is assumed.

`garch_challenger.py` fits and builds an immutable typed volatility Signal.
`garch_service.py` provides explicit provider-history generation, repository retry,
and subsequent Outcome refresh. `garch_evaluation.py` computes paired errors;
`garch_model_lab.py` presents them through the existing Model Lab.
No changes to Volatility Context calculations, typed Signal/Outcome storage,
Observation Engine policy, options scoring, or normal scan execution are required.

## Dependency and exact model

Pinned `arch==8.0.0` (NCSA license, Python >=3.10). Local validation uses Windows
CPython 3.12.10, NumPy 2.5.3, SciPy 1.18.1, and Streamlit 1.63.0. `pip check` passes.
CI continues to use Python 3.12 and installs requirements; Linux CI was not run
locally. The numerical dependencies are not fully locked, so cross-platform fits
may differ slightly. Signals retain library, NumPy, and SciPy versions.

Specification: zero-mean Gaussian GARCH(1,1), no asymmetric term, power 2,
`rescale=False`, percent log returns, maximum-likelihood library fitting with
`tol=1e-8`, maximum 1000 optimizer iterations. No model search or tuning.

`r_t = 100 * (log(C_t) - log(C_(t-1)))`

`h_t = omega + alpha * r_(t-1)^2 + beta * h_(t-1)`

Persisted components include omega (percent-return squared), alpha, beta,
alpha+beta (`persistence`), final conditional annualized volatility, all forecasts,
and frozen trailing RV20/RV10. Diagnostics include optimizer status/message,
iterations, warnings, input hash, dates, count, source, and model conventions.

Identity: `garch-volatility` / `garch-1-1-v0.1`; volatility family;
direction `not_applicable`, conviction 0, confidence absent. UUIDv5 derives from
model ID/version, normalized ticker, and analysis date. A service retry loads the
persisted Signal without fetching or fitting again. Conflicting immutable writes
raise rather than overwrite.

References: [arch analytic forecasting](https://arch.readthedocs.io/en/latest/univariate/forecasting.html)
and [arch 8.0.0 package](https://pypi.org/project/arch/8.0.0/).

## History and point-in-time policy

Request 800 calendar days ending at the established most recent completed session
strictly before the analysis date. Use at most the latest 501 closes / 500 returns,
requiring at least 253 closes / 252 returns. This is an explicit one-year minimum
for estimating persistence, with roughly two years preferred; RV20's short window
is not a defensible training window for this three-parameter challenger. These are
fixed research policy choices, not empirically optimized thresholds or guarantees
of estimation quality. Symbols with shorter histories produce no forecast.

Only finite positive daily closes on US equity sessions enter training. Require
contiguous selected sessions and a fresh final completed close; reject duplicates,
missing sessions, stale history, and malformed data. Exclude same-day and future
closes before fitting, including historical replay. This deliberately excludes the
analysis day's close even if run after market close. Future service analysis dates
are rejected. A historical replay still uses today's provider revision of historical
prices: corporate actions, revisions, and historical data availability are not
reconstructed. This is cutoff-safe replay, not a vintage-data archive.

## Forecasts and baseline

The existing volatility Outcome starts at the first session close on/after the
Signal analysis date, then measures H subsequent returns. Training stops at the
prior completed close. Therefore forecast 61 steps and aggregate **steps 2..H+1**,
for H = 5, 20, 60:

`forecast_H = sqrt(252 * mean(h_2, ..., h_(H+1))) / 100`

Under the zero-mean model, returns are uncorrelated and the expected sample
variance equals the mean conditional variances. This forecasts the square root
of expected sample variance, **not** the expectation of sample standard deviation;
the distinction can create bias when evaluated in volatility units.

Comparator: frozen trailing RV20 = sample standard deviation of the last 20 log
returns times sqrt(252). Persist the same value for use at all three horizons.
No future RV20, fitted comparator, or separately selected baseline sample is used.

## Evaluation and interpretation

Reuse existing volatility Outcomes, including full session verification and
`evaluated`, `not_yet_eligible`, `missing_data`, and `error` statuses. Explicit refresh
caps provider data at the latest completed session, even with a future requested
through-date. Refresh changes Outcomes using existing repository semantics; it
never changes the frozen Signal or forecasts.

For each mature valid pair: signed error = forecast - actual, absolute error,
squared error, and corresponding frozen-baseline errors. Summaries per horizon:
count, coverage, MAE, RMSE, bias, median absolute error, baseline equivalents,
and GARCH MAE minus baseline MAE. Negative difference favors GARCH on that sample.
Invalid or unevaluated pairs are omitted from both models' metrics. Empty metrics
are absent (`None`), never fabricated zeros. Coverage denominator is persisted
GARCH Signals, not all attempted fits; failed fits have no durable Signal and
are not represented in this scorecard. This introduces selection limitations.

Fewer than 30 pairs are explicitly preliminary; larger counts remain descriptive,
without significance claims. Overlapping windows are dependent. Synthetic data is
generated by a GARCH process and cannot establish out-of-sample market superiority.
The fixture includes individual wins and losses against persistence even though
its aggregate MAE favors GARCH. No production promotion is supported by this evidence.

## Failure and operational policy

No fallback Signal: insufficient history, provider failure, missing dependency,
optimizer exception/non-convergence, invalid parameters, and numerical forecast
failure return explicit statuses. Require omega > 0, alpha/beta >= 0, all finite,
and alpha+beta < 0.995; equality and larger values are rejected as nonstationary
or near-boundary. The conservative 0.995 cutoff is fixed policy, not a tuned result.
Forecast variances and final volatility must be finite and positive. Flat returns
are rejected. Warnings are retained; successful optimizer status does not prove
economic validity. The UI displays failure diagnostics; failed attempts are not a
durable audit ledger. Storage/comparison failures remain visible and retryable.

Fit only on explicit request, one security/date at a time. Normal scans and ordinary
UI reruns do not fit. A valid stored forecast acts as the permanent reuse boundary.
One synthetic CLI run measured 1.389 seconds for the cold first fit (including lazy
library import) and 0.027 seconds warm for the second; no network latency included.
Provider GET timeout is 15 seconds; fitting has an iteration cap, not a wall-clock
deadline. The UI blocks during a requested fit. Large-universe throughput and live
provider latency were not benchmarked.

## Observation Engine and UI

After Signal persistence, call the unchanged v0.4 comparison engine. Compatible
model/version lineage and immutable first-observation receipts are preserved.
GARCH has no transition rule metadata, so it generates zero Observation Events.
No event is invented for a forecast delta or failure. Signal and comparison writes
remain separate transactions; a retry can recover a missing comparison receipt.

Model Lab provides an explicit run form, model/family filtering, training depth,
parameters, forecasts, RV20, diagnostics, paired metrics, Outcome ledger, and explicit
selected-Signal Outcome refresh. Direction is N/A and conviction is zero. Volatility
Context remains separately selectable. Coverage and small-sample limits are visible.

## Validation

Initial implementation validation using the recovered worktree `.venv` (historical results; final post-correction validation is recorded below):

- Final focused GARCH run: **36 passed in 4.28s**.
- Combined GARCH, volatility, typed family, Signal foundation/integration,
  Observation comparisons/engine, and Model Lab: **107 passed in 10.07s**.
- Standard CI-equivalent `python -m pytest -q -m "not authoritative_rce_evidence"`:
  **575 passed, 3 deselected, 21 subtests passed in 29.72s**. Local commands also
  used `-p no:cacheprovider` and an isolated `--basetemp=.local-validation/...`;
  test selection was unchanged.
- `python -m compileall -q app.py src scripts tests`: pass.
- `git diff --check`: pass; staged new files also checked before commit.
- `python -m pip check`: no broken requirements.
- Synthetic fixture executed and rerun: four Signals, six Outcomes, zero Events.
- Model Lab exercised with Streamlit AppTest, including GARCH/context selection;
  no browser visual inspection or live provider/PostgreSQL run performed during initial recovery. Subsequent product-owner live acceptance is recorded below.

Authoritative RCE files, markers, workflow, and evidence contract remain unchanged.

## Exact manual acceptance (PowerShell, no provider credentials required)

From this worktree, use its recovered `.venv`. Choose a new filename if preserving
an earlier acceptance database; never delete/reset it. The fixture appends and
accepts identical reruns, while conflicting immutable content is rejected.

```powershell
.venv/Scripts/python.exe -m scripts.seed_garch_acceptance --database .local-validation/garch-manual-v05.sqlite
$env:RESEARCH_REPOSITORY_BACKEND = 'sqlite'
$env:RESEARCH_SQLITE_PATH = (Join-Path (Get-Location) '.local-validation/garch-manual-v05.sqlite')
$env:RCE_PROVIDER = 'mock'
.venv/Scripts/python.exe -m streamlit run app.py
```

1. CLI reports `SYNTH-A` and `SYNTH-B` valid, two paired observations per horizon,
   coverage 1.0. All results are visibly synthetic developer evidence.
2. Open Model Lab, select Volatility and `garch-volatility / garch-1-1-v0.1`.
   Expect two Signals dated 2024-01-02, 500 training returns ending 2023-12-29,
   Direction N/A, conviction 0, omega/alpha/beta/persistence and three forecasts.
3. SYNTH-A's 5-session forecast is approximately 0.162004; its baseline is 0.151816.
   Metrics have two pairs per horizon, preliminary labels, and six evaluated Outcomes.
   Rounded GARCH/baseline MAEs: 5d 0.030621/0.043489;
   20d 0.039958/0.055859; 60d 0.016114/0.053703.
4. Inspect raw diagnostics for source, hash, optimizer status, cutoff and versions.
   Confirm the no-GARCH-events notice. Switch to Volatility Context and verify its
   two separate Signals and ordinary context presentation.
5. Rerun the seeder command and refresh the app. Counts remain four total Signals
   (two per model), six Outcomes, zero Observation Events. Stop Streamlit with Ctrl+C.
6. Automated focused tests cover insufficient history, gaps, stale/invalid closes,
   dependency failure, optimizer failure, bad parameters, frozen service retries,
   future exclusion, and immature/missing Outcomes. To reproduce:
   `.venv/Scripts/python.exe -m pytest -q tests/test_garch_challenger.py`.

Optional live-provider acceptance: with normal Tradier credentials and a separate
research database, submit a ticker/date through the form; inspect status and elapsed
time, then submit the same date and verify `retry` with `refitted: false`. Refresh
selected Outcomes explicitly after maturity. A provider or fit failure is a valid
visible result, not permission to invent a forecast. No live-provider run was made
during recovery. Subsequent live reacceptance completed successfully; see the final acceptance record below.

## v0.5 live acceptance finding: NVDA, 2026-09-16

The product owner reported `provider_history_failure` for an on-demand NVDA
forecast. The Model Lab diagnostics identify `model_id=garch-volatility`,
`model_version=garch-1-1-v0.1`, `analysis_date=2026-09-16`,
`source=tradier-daily-history`, and the exact error `Missing training session
2025-01-09`. This confirms the rejection occurred in GARCH's strict history
validation, rather than during the provider request. Code inspection found the
calendar defect that caused this result: the 800-calendar-day request starts
2024-07-08 and includes 2025-01-09, which the shared calendar incorrectly
classified as a required trading session. NYSE and Nasdaq closed their U.S.
equity markets that day for President Jimmy Carter's National Day of Mourning
([NYSE notice](https://www.nyse.com/publicdocs/nyse/markets/american-options/rule-interpretations/2025/National_Day_of_Mourning_20250102.pdf),
[Nasdaq announcement](https://ir.nasdaq.com/news-releases/news-release-details/nasdaq-announces-closure-its-us-markets-honor-national-day-0)).
No 2025-01-09 provider bar is therefore expected. The strict GARCH gap check
would reject otherwise contiguous history with `Missing training session
2025-01-09`. The reported diagnostic confirms this was the live failure. The
raw provider response was not supplied, but a bar is not expected on a full-day
exchange closure. Model Lab reported no usable GARCH forecast, and no Signal
was created, as required by the fail-closed policy. The defect was the
calendar's incorrect classification of the closure; the forecast failure
policy behaved correctly.

GARCH, Volatility Context's completed-bar cutoff, Signal Outcomes, and the
Observation Engine's market-day status all use `src.market_calendar`. GARCH did
not bypass a separate authoritative calendar. The shared calendar now records
the one-off full-day closure; no GARCH-specific calendar exception was added.
The contiguous-history rule and point-in-time cutoff are unchanged. Calendar
tests check January 8/9/10; a GARCH regression accepts the legitimate closure
and rejects a missing January 8 provider bar with `provider_history_failure`
and no Signal. Existing tests covered recurring holidays and weekends, not
this class of closure. A Signal Outcome regression proves that a one-session
horizon starting January 8 ends January 10, appropriately excluding the
closure. Existing Volatility Context completed-bar and other Signal Outcome
session-counting regressions remain unchanged and pass.
Review of exchange calendar announcements for the 2024-07-08 through
2026-09-15 request interval identified no other one-off full-day U.S. equity
closure. This is a bounded source review, not a live provider audit.

Previously reported post-correction validation on 2026-09-19 (historical):

- focused GARCH: **37 passed**;
- market calendar/session: **13 passed**;
- Volatility Context: **5 passed**;
- Signal/Outcome: **30 passed**;
- Observation Engine: **35 passed**;
- Model Lab: **2 passed**;
- CI-equivalent suite: **578 passed, 3 deselected, 21 subtests passed**;
- `python -m compileall -q app.py src scripts tests`: passed;
- `git diff --check`: passed.

## Final validation (2026-09-29)

Re-run in the worktree's existing Windows CPython 3.12.10 `.venv`; no dependency
installation or changes to authoritative RCE selection were needed. Each pytest
command used `-p no:cacheprovider` and an isolated
`--basetemp=.local-validation/final-20260929-<suite>` to preserve historical artifacts.

| Suite | Files / selection | Final result |
| --- | --- | --- |
| Focused GARCH | `tests/test_garch_challenger.py` | 37 passed in 24.96s |
| Calendar/session | `tests/test_market_calendar.py`, `tests/test_technical_analysis.py` | 13 passed in 0.13s |
| Volatility Context | `tests/test_volatility_context.py` | 5 passed in 0.20s |
| Signal/Outcome | `tests/test_signal_foundation.py`, `tests/test_signal_integration.py`, `tests/test_typed_signal_families.py` | 30 passed in 9.73s |
| Observation Engine | `tests/test_observation_comparisons.py`, `tests/test_scheduled_observation_engine.py` | 35 passed in 9.48s |
| Model Lab | `tests/test_model_lab_streamlit.py` | 2 passed in 6.52s |
| Full CI-equivalent | `python -m pytest -q -m "not authoritative_rce_evidence"` | 578 passed, 3 deselected, 21 subtests passed in 75.76s |

`python -m compileall -q app.py src scripts tests` passed.
`git diff --check` passed. `python -m pip check` reported no broken requirements.
Authoritative RCE evidence/workflow and POE-B001 through POE-B005 remain unchanged.

## Successful live NVDA reacceptance: analysis date 2026-09-19

Product-owner manual acceptance = **PASS**. The product owner completed the live
Model Lab run after the shared-calendar correction and supplied the following
accepted evidence. This finalization did not fetch provider history or refit it.

| Field | Accepted first-run result |
| --- | --- |
| Security / source | NVDA / `tradier-daily-history` |
| Analysis date | `2026-09-19` |
| Status | `valid` |
| Model ID / version | `garch-volatility` / `garch-1-1-v0.1` |
| Observation count | 500 returns |
| Training start / end | `2024-09-19` / `2026-09-18` |
| Library / version | `arch` / `8.0.0` |
| Convergence flag | 0 |
| Optimizer | terminated successfully |
| Warnings | `[]` |

The Signal persisted in Model Lab with no `Missing training session 2025-01-09`
error. Observed approximate values were current conditional volatility **0.408**,
5d forecast **0.4048**, 20d forecast **0.4161**, 60d forecast **0.4346**, and
persistence **0.9726**. These rounded values document the observed implementation,
not forecast performance.

The second identical request returned **`status=retry`, `refitted=false`**.
It reused the immutable persisted Signal. The preserved live SQLite database
`.local-validation/garch-live-nvda-v05.sqlite` corroborates the valid NVDA Signal
and training provenance; finalization inspected it read-only and preserved it.
The retry UI result is product-owner evidence, not a separate persisted fit.

At live acceptance, forward 5/20/60 realized-volatility Outcomes were not yet
mature and were correctly absent. This is a record of acceptance-time state;
finalization does not refresh Outcomes or claim that all horizons remain immature
on its later date. Initial synthetic acceptance remains documented above.

Remaining non-blocking risks: provider revisions and corporate-action adjustments
are not reconstructed; the handwritten shared calendar needs maintenance for
future exceptional closures; numerical dependencies are not fully locked;
cross-platform fits can differ; failed fits are excluded from scorecard coverage;
overlapping windows are dependent; fitting has no wall-clock deadline; and live
latency/large-universe throughput and PostgreSQL acceptance remain unbenchmarked.
Synthetic and single-security live acceptance establish behavior, not forecast
value. Mature out-of-sample comparisons and statistical evaluation remain deferred,
along with tuning, model search, directional Signals, automated fitting, trading,
brokerage integration, production promotion, and v0.6 work.
