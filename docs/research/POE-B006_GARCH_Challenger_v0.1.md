# POE-B006 — GARCH Challenger v0.1

Status: implemented research challenger; product-owner manual acceptance pending.
This is synthetic developer evidence, not authoritative RCE evidence or a claim of market predictive value.

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

Local results using the recovered worktree `.venv`:

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
  no browser visual inspection or live provider/PostgreSQL run performed.

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
during recovery. Product-owner acceptance remains pending.
