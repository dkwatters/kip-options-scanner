# POE-B004 — Volatility Context v0.1

Status: implementation evidence; not a frozen benchmark corpus.

## Brief and decision

This milestone implements the v0.3 Volatility Context brief as an additive typed-family capability. The architectural decision is to calculate context from the same dated market-history response already used by TAM, carry it transiently to the shared technical-observation persistence boundary, archive the unchanged TAM row, and atomically persist independent Technical Setup and Volatility Context Signals.

## Chosen measures

The versioned baseline uses annualized 10/20-session close-to-close realized volatility, 14-session ATR%, 20-session two-standard-deviation Bollinger Bandwidth, a 252-observation rolling RV20 empirical percentile with a 60-observation minimum, fixed 25/70/90 regime boundaries, and a fixed RV10/RV20 0.90/1.10 trend band.

## Rejected alternatives

- Absolute volatility regime cutoffs were rejected because self-relative context is more comparable across securities.
- Full-sample percentile ranks were rejected as point-in-time unsafe.
- Weighted scoring was rejected as less explainable than a direct short/long comparison.
- Data quality was not relabeled as confidence.
- Directional abstention was rejected for missing non-directional analysis.
- GARCH-family and implied-volatility comparisons were deferred to preserve a simple baseline.

## Signal and Outcome changes

Production workflows with valid OHLC history emit `volatility-context · volatility-context-v0.1` alongside unchanged `technical-setup-score · technical-setup-signal-v0.1.1`. Volatility Signals use N/A direction, zero conviction, null confidence, flexible components/metadata, and deterministic identity. Volatility Outcomes persist annualized subsequent realized volatility for 5/20/60 verified sessions without directional correctness.

## Evidence and acceptance

Automated evidence is in `tests/test_volatility_context.py` plus the existing Signal/Outcome, typed-family, integration, technical scan, Universe Analysis, Opportunity Discovery, and Model Lab suites. Tests cover calculations, thresholds, insufficient history, future-data exclusion by cutoff, deterministic identity, typed round-trip, verified sessions/holidays, missing data, immaturity, production coexistence, idempotency, and non-directional presentation. Final command results and implementation commits are recorded in the completion report and Git history.

### Pre-PR completed-bar correction

Independent acceptance found that the initial implementation reused TAM's same-day history cutoff for Volatility Context. A provider-supplied analysis-date OHLC row could therefore represent an in-progress daily bar. The corrective decision preserves TAM behavior and gives Volatility Context its own conservative boundary: the most recent verified U.S. equity session strictly before the analysis date. Provider rows on weekends, supported holidays, or after that boundary are rejected. Regression evidence proves an extreme same-day bar cannot alter RV10, RV20, ATR%, Bollinger Bandwidth, percentile, regime, or trend, and covers replay, weekend, and holiday behavior. Outcome documentation now states explicitly that 5/20/60 sessions mean 5/20/60 log returns from 6/21/61 closes.

### Pre-merge CI correction

The initial PR check invoked the installed `pytest` console entry point directly. On the GitHub Actions Python 3.12 runner, that launcher did not place the checked-out repository root on `sys.path`, so collection stopped with 39 import errors before any tests executed. The workflow now invokes `python -m pytest -q` from the unchanged repository-root working directory, using the configured interpreter and making the repository modules importable without changing application imports, test semantics, or RCE evidence. The same plain-entry-point failure reproduced independently in the accepted baseline workflow.

The subsequent clean-runner execution established that three integrity tests require the exact gitignored `data/research/rce_benchmarks.sqlite` binary and its frozen SHA-256, not merely a semantically rebuilt database. The tracked fixtures can reconstruct the benchmark rows but not that frozen binary identity. Standard PR CI therefore runs all reproducible tests while deselecting only the explicitly marked `authoritative_rce_evidence` tests. A separate manual `RCE Evidence Validation` workflow provisions the controlled artifact through the `rce-evidence` environment, verifies SHA-256 `48ea2c839dee93a995d9cfb21869f015d7a5b63b18a7ee2e4591b04a7da235c8`, and then runs those tests without weakening their assertions. Streamlit AppTest smoke paths use a bounded ten-second test timeout after repeated runs demonstrated occasional default three-second runner timeouts under load; application behavior remains unchanged.

## Baseline/challenger rationale

Future GARCH-family forecasts must demonstrate value relative to this simpler deterministic volatility context rather than merely producing sophisticated-looking outputs. This release neither uses Outcome data to tune thresholds nor freezes a new benchmark corpus.
