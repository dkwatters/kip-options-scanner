# Research Notebook

## Purpose

This notebook captures empirical observations and model research over time for the Stock Screener project.

It records observed behavior, hypotheses, experiments, conclusions, and future research questions. It is intended as a permanent research journal, not developer documentation.

---

## Milestone Log

### Milestone M3 - Autonomous Observation Achieved

Date: 2026-07-03

Definition:
The first successful end-to-end execution of an unattended Study Protocol resulting in correctly archived observations, accurate protocol progress, and synchronized Research Dashboard display.

Evidence:

- SP-001 produced scheduled observations for 10:00 ET, 12:00 ET, and 14:00 ET.
- Each observation archived with `run_mode = scheduled`.
- Study Protocol Progress correctly displayed all three scheduled observations as recorded.
- Manual scans remain excluded from scheduled study metrics.

Status:
Complete

---

### Milestone M4 - Technical Analysis Model v0.1 Added

Date: 2026-07-06

Definition:
The first independent stock-level technical research layer was added as Technical Analysis Model v0.1.

Evidence:

- Technical observations archive to `technical_characterization`.
- Initial indicators include price, 20/50/200-day SMA relationships, RSI 14, MACD, and 20-day realized volatility when price history supports it.
- TAM rows are linked to Opportunity Scans by `scan_id` when generated during scans.
- TAM remains research metadata and does not alter CQM scoring, Opportunity Discovery ranking, QED, thresholds, or Evaluation Profile behavior.

Status:
Complete

---

### Milestone M5 - Technical Analysis Explorer v0.1 Added

Date: 2026-07-06

Definition:
A read-only Technical Analysis Explorer was added to visualize and QA TAM output.

Evidence:

- The explorer reads existing rows from `technical_characterization`.
- It shows latest TAM observations, filters by ticker, state, latest scan, and optional `scan_id`, and surfaces summary cards plus QA distributions.
- The explorer is observational only and does not alter options filtering, ranking, CQM scoring, QED, thresholds, or Evaluation Profile behavior.

Status:
Complete

---

## Observation Log

### Observation 001

Observation ID: OBS-001

Date: 2026-07-01

Study Protocol: SP-001 Intraday Technology Growth AI Calls

Observation: Model architecture separated Security evaluation from Contract evaluation.

Evidence: The current research workflow distinguishes Universe and Evaluation Profile context from the Contract Quality Model, and archives evaluated option contracts separately from ticker-level security characterization.

Confidence: High

Follow-up Questions: Does this separation remain sufficient when future Technical Model or Trade Fit Model components are introduced?

### Observation 002

Observation ID: OBS-002

Date: 2026-07-01

Study Protocol: SP-001 Intraday Technology Growth AI Calls

Observation: Passing contracts are concentrated among a relatively small subset of securities.

Evidence: Archived scans write ticker-level security characterization rows, allowing comparison between total evaluated contracts and passing counts by ticker. Initial scan results showed passing contracts as a small fraction of all evaluated contracts.

Confidence: Medium

Follow-up Questions: Which securities repeatedly produce passing contracts across multiple intraday scans, and is the concentration stable across days?

### Observation 003

Observation ID: OBS-003

Date: 2026-07-01

Study Protocol: SP-001 Intraday Technology Growth AI Calls

Observation: Volume and Delta dominate Near Misses.

Evidence: Quality diagnostics and rule-evaluation exports identify failed rules for near-miss contracts. Prior diagnostic review indicated Volume and Delta were common limiting rules among Near Misses.

Confidence: Medium

Follow-up Questions: Does the dominant Near Miss rule mix change by time of day, ticker group, or DTE range?

### Observation 004

Observation ID: OBS-004

Date: 2026-07-01

Study Protocol: SP-001 Intraday Technology Growth AI Calls

Observation: Opportunity Discovery appears sensitive to time of day.

Evidence: SP-001 was created specifically to observe intraday behavior at suggested 10:00, 12:00, and 14:00 Eastern scan times. This sensitivity is an observed research concern, not yet a quantified conclusion.

Confidence: Low

Follow-up Questions: How do passing count, near-miss count, rejected count, liquidity measures, and Delta distribution vary across the proposed intraday scan times?

### Observation 005

Observation ID: OBS-005

Date: 2026-07-01

Study Protocol: SP-001 Intraday Technology Growth AI Calls

Observation: SQLite Research Repository successfully archives scans.

Evidence: A manual research scan archived one opportunity scan with linked rows in opportunity_scans, evaluated_contracts, rule_evaluations, and security_characterization. The latest verified scan wrote 23,029 evaluated_contracts rows, 92,116 rule_evaluations rows, and 66 security_characterization rows.

Confidence: High

Follow-up Questions: What repository summaries are most useful for recurring research review without adding premature trend conclusions?

### Observation 006

Observation ID: OBS-006

Date: 2026-07-06

Study Protocol: SP-001 Intraday Technology Growth AI Calls

Observation: Stock-level technical characterization is now captured independently from option contract quality evaluation.

Evidence: TAM rows persist separately in `technical_characterization`, while contract-level rows and rule evaluations continue to be archived through the existing CQM path.

Confidence: High

Follow-up Questions: Do specific TAM states correlate with later option quality, opportunity persistence, or forward outcomes across repeated scans?

---

## Hypothesis Log

### Template

Hypothesis ID:

Description:

Supporting Evidence:

Conflicting Evidence:

Status:

Planned Experiment:

---

## Study Protocols

### SP-001

Intraday Technology Growth AI Calls

Purpose:
Characterize intraday behavior of the Evaluation Profile.

---

## Evaluation Profile History

### Technology Growth / Momentum AI

Version 0.1

Status:
Baseline

---

## Major Findings
