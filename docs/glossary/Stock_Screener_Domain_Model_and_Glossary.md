# Stock Screener Domain Model and Glossary

## 1. Executive Summary

| Entity Name | One-Sentence Definition | Primary Question It Answers | Primary Module(s) |
| --- | --- | --- | --- |
| Evaluation Profile | A versioned analytical configuration that defines how a population should be evaluated. | Which models, settings, and research context are active? | `src/evaluation_profile.py` |
| Reference Universe | The defined population of securities being evaluated. | Which securities are in scope? | `src/universe.py`, `data/*.csv` |
| Security | A tradable underlying instrument such as an equity or ETF. | What underlying asset is being studied? | `src/universe.py`, `app.py` |
| Option Contract | A listed derivative contract for a security. | What specific contract is being evaluated? | `app.py`, `src/contract_quality.py` |
| Contract Quality Model (CQM) | The model that evaluates option contract quality using contract-level rules. | Is this contract structurally acceptable? | `src/contract_quality.py`, `src/contract_scoring.py` |
| Technical Opportunity Model (TOM) | A planned model for evaluating underlying security setup quality. | Is the security technically interesting? | Planned |
| Opportunity Discovery | The workflow that evaluates a universe and ranks candidate contracts. | What opportunities are visible in the current scan? | `app.py`, `src/opportunity_ranking.py` |
| Quick Evaluation (QED) | A diagnostic view of one scan's quality-engine behavior. | What happened during this scan? | `src/quality_diagnostics.py`, `app.py` |
| Opportunity Scan | One completed Opportunity Discovery run. | What was observed at one point in time? | `src/research_repository.py`, `research_scan.py` |
| Study Protocol | A repeatable observational study definition. | Why and how is this scan being repeated? | `src/study_protocol.py` |
| SQLite Research Repository | The local persistent archive for completed scans and linked research data. | Where is scan evidence stored? | `src/research_repository.py` |
| Research Notebook | The permanent research journal. | What observations, hypotheses, and conclusions have accumulated? | `docs/research/Research_Notebook.md` |
| Security Characterization | A ticker-level summary of scan behavior. | How did each security behave in a scan? | `src/research_repository.py` |
| Rule Characterization | A summary of rule outcomes and failures. | Which rules passed, failed, or constrained opportunities? | `src/rule_evaluation.py`, `src/quality_diagnostics.py` |
| Near Miss Analysis | Analysis of contracts that narrowly fail quality requirements. | What almost passed, and why? | `src/contract_quality.py`, `src/quality_diagnostics.py` |
| Historical Repository | The accumulated research evidence across scans. | What has been observed over time? | `data/research/opportunity_scans.sqlite` |

---

## 2. Business Entities

### Evaluation Profile

Definition: A versioned analytical configuration that identifies the active models, universe context, scan defaults, ranking preferences, and output preferences.

Purpose: Provide a stable research and operational context for repeated evaluations.

Questions Answered: Which analytical configuration is active? Which model versions are being used? Which defaults should scans use?

Inputs: Model references, default scan parameters, universe name, ranking preferences, output preferences, metadata.

Outputs: Export metadata, scan context, profile identity.

Owns: Evaluation configuration, model references, profile version.

Does NOT Own: Contract scoring logic, security universe contents, market data, research conclusions.

Relationships: Orchestrates Contract Quality Model and future Technical Opportunity Model. Associated with Study Protocols and Opportunity Scans.

Module(s): `src/evaluation_profile.py`

Status: Stable

### Reference Universe

Definition: A named, explicit population of securities selected for evaluation.

Purpose: Define the population being observed so research results are interpretable.

Questions Answered: Which securities are in scope? How large is the study population? What population was used for a scan?

Inputs: CSV rows with symbol, name, sector, and enabled flag.

Outputs: Enabled security symbols and display metadata.

Owns: Population membership.

Does NOT Own: Contract evaluation, ranking, model thresholds, market-data retrieval.

Relationships: Used by Opportunity Discovery and Study Protocols. Contains Securities.

Module(s): `src/universe.py`, `data/technology_growth_ai_v1.csv`, `data/universe_default.csv`

Status: Stable

### Security

Definition: A tradable underlying instrument, usually an equity or ETF, for which option contracts may be evaluated.

Purpose: Serve as the underlying object of analysis and contract discovery.

Questions Answered: What underlying instrument is being evaluated? What contracts are associated with it?

Inputs: Symbol, name, sector, quote data, option expiration data.

Outputs: Underlying price context, option-chain retrieval context, security-level research summaries.

Owns: Security identity and underlying market context.

Does NOT Own: Option-contract rule outcomes, portfolio decisions, research conclusions.

Relationships: Belongs to a Reference Universe. Has many Option Contracts. Produces Security Characterization rows.

Module(s): `src/universe.py`, `app.py`

Status: Stable

### Option Contract

Definition: A listed option instrument with expiration, strike, type, pricing, liquidity, and Greek values.

Purpose: Provide the concrete contract-level unit evaluated by the Contract Quality Model.

Questions Answered: Is this contract liquid enough? Is its delta suitable? Is the spread acceptable? Is it a passing, near-miss, or rejected contract?

Inputs: Option chain data, expiration date, underlying price, current date.

Outputs: Contract quality fields, classification, rule outcomes, quality score.

Owns: Contract-level observable fields and CQM-derived evaluation outputs.

Does NOT Own: Security-level attractiveness, technical setup, outcome tracking.

Relationships: Belongs to a Security. Evaluated by the Contract Quality Model. Archived in Opportunity Scans.

Module(s): `app.py`, `src/contract_quality.py`, `src/contract_scoring.py`

Status: Stable

### Contract Quality Model (CQM)

Definition: The current contract-level model that evaluates option contracts using delta, spread, open interest, volume, and quality-score logic.

Purpose: Characterize whether a contract meets structural quality requirements.

Questions Answered: Does this contract pass quality rules? Which rules failed? How strong is the contract by current scoring?

Inputs: Option contract fields, current date, expiration, underlying price.

Outputs: Pass/fail fields, quality score, rule margins, rule score breakdown.

Owns: Contract quality rules, thresholds, contract-level scoring.

Does NOT Own: Security technical evaluation, universe membership, outcome attribution, opportunity concentration.

Relationships: Used by Opportunity Discovery, QED, Rule Characterization, Near Miss Analysis, and the Research Repository.

Module(s): `src/contract_quality.py`, `src/contract_scoring.py`

Status: Stable

### Technical Opportunity Model (TOM)

Definition: A planned security-level model for evaluating whether an underlying security has an attractive technical setup.

Purpose: Separate security attractiveness from contract quality.

Questions Answered: Is this security technically interesting? What market or indicator context supports that view?

Inputs: Planned technical indicators, price behavior, market context.

Outputs: Planned security-level opportunity evaluation.

Owns: Security-level technical evaluation.

Does NOT Own: Contract liquidity, contract delta fit, contract spread, CQM rule scoring.

Relationships: Expected to be orchestrated by Evaluation Profiles alongside CQM.

Module(s): Planned

Status: Emerging

### Opportunity Discovery

Definition: The workflow that evaluates a Reference Universe, filters contracts, applies the CQM, and ranks visible candidates.

Purpose: Identify passing or near-miss contract candidates for research review.

Questions Answered: What opportunities are visible now? Which contract is the best passing or near-miss candidate per security?

Inputs: Reference Universe, option type, DTE range, market data, Evaluation Profile.

Outputs: Opportunity table, evaluated contracts, discovery errors, archived Opportunity Scan.

Owns: Scan execution flow and candidate selection from already-evaluated contracts.

Does NOT Own: CQM thresholds, universe membership, future outcome claims.

Relationships: Uses Reference Universe, Securities, Option Contracts, CQM, and Research Repository.

Module(s): `app.py`, `src/opportunity_ranking.py`, `research_scan.py`

Status: Stable

### Quick Evaluation (QED)

Definition: A diagnostic view that summarizes the behavior of the quality engine during a single scan.

Purpose: Provide immediate interpretability for scan outcomes.

Questions Answered: How many contracts passed, nearly passed, or failed? Which rules constrained results? What distributions describe the scan?

Inputs: Evaluated contract rows and opportunity rows.

Outputs: Diagnostic summaries, distributions, rule failure summaries, population profiles.

Owns: Single-scan diagnostic summaries.

Does NOT Own: Longitudinal conclusions, outcome attribution, model changes.

Relationships: Consumes Opportunity Scan results and supports Research Notebook observations.

Module(s): `src/quality_diagnostics.py`, `app.py`

Status: Stable

---

## 3. Research Entities

### Opportunity Scan

Definition: One completed Opportunity Discovery run with scan metadata, evaluated contracts, rule evaluations, and security characterization.

Purpose: Preserve a point-in-time observation for future research.

Questions Answered: What was evaluated? When was it evaluated? What were the scan results?

Inputs: Scan timestamp, universe, Evaluation Profile, Study Protocol metadata, evaluated rows.

Outputs: Repository rows linked by `scan_id`.

Owns: Scan identity and point-in-time evidence.

Does NOT Own: Model thresholds, future outcomes, research conclusions.

Relationships: Produced by Opportunity Discovery. Archived by SQLite Research Repository. Associated with Study Protocols.

Module(s): `src/research_repository.py`, `research_scan.py`

Status: Stable

### Security Characterization

Definition: A ticker-level summary of contract evaluation outcomes within a scan.

Purpose: Identify how each security behaved during an Opportunity Scan.

Questions Answered: How many contracts were evaluated for this security? How many passed, nearly passed, or failed? Which failure pattern dominated?

Inputs: Evaluated contract rows grouped by ticker.

Outputs: Per-security counts, rates, best score, average score, dominant failures.

Owns: Scan-level security summaries.

Does NOT Own: Technical setup, future security performance, portfolio decisions.

Relationships: Derived from Opportunity Scans and stored in the Research Repository.

Module(s): `src/research_repository.py`

Status: Emerging

### Rule Characterization

Definition: A research summary of how individual rules behaved across evaluated contracts.

Purpose: Understand which CQM rules drive pass, near-miss, and rejection outcomes.

Questions Answered: Which rules fail most often? Which rules constrain otherwise promising contracts? Are rule outcomes stable?

Inputs: Rule evaluations and evaluated contract rows.

Outputs: Rule failure distributions, rule contribution summaries, threshold-distance summaries.

Owns: Rule behavior descriptions.

Does NOT Own: Rule threshold changes or optimization decisions.

Relationships: Uses CQM outputs and Research Repository rule_evaluations.

Module(s): `src/rule_evaluation.py`, `src/quality_diagnostics.py`

Status: Emerging

### Near Miss Analysis

Definition: Analysis of contracts that fail a limited number of quality rules and are close to passing.

Purpose: Characterize almost-acceptable contracts without changing the model.

Questions Answered: Which rule prevented a contract from passing? How far from passing was it? Which near-miss patterns recur?

Inputs: Evaluated contracts, failed rules, threshold distances.

Outputs: Near-miss counts, failure labels, margin summaries.

Owns: Near-miss classification and interpretation.

Does NOT Own: Contract promotion, threshold changes, outcome claims.

Relationships: Uses CQM rule outputs and supports Hypotheses.

Module(s): `src/contract_quality.py`, `src/quality_diagnostics.py`, `app.py`

Status: Stable

### Excellent Contract Characterization

Definition: Planned characterization of contracts that strongly satisfy quality criteria.

Purpose: Define empirical traits of high-quality contracts.

Questions Answered: What do excellent contracts have in common? Are excellent contracts concentrated in certain securities or times?

Inputs: Passing contracts, quality scores, rule margins, scan metadata.

Outputs: Planned high-quality contract profiles.

Owns: Research description of excellent contracts.

Does NOT Own: Trading recommendations or outcome claims.

Relationships: Builds on CQM outputs and Historical Repository data.

Module(s): Planned

Status: Emerging

### Opportunity Concentration

Definition: The degree to which passing or high-quality opportunities cluster within a small subset of securities.

Purpose: Characterize whether opportunity availability is broad or concentrated.

Questions Answered: Are opportunities spread across the universe or concentrated? Which securities dominate opportunity production?

Inputs: Security Characterization rows and Opportunity Scan summaries.

Outputs: Concentration observations and planned metrics.

Owns: Distributional research about opportunity sources.

Does NOT Own: Universe selection changes or model threshold changes.

Relationships: May produce OCI and ODI metrics.

Module(s): Planned; partially supported by `src/research_repository.py`

Status: Emerging

### Opportunity Concentration Index (OCI)

Definition: A planned metric describing how concentrated opportunities are among securities.

Purpose: Quantify opportunity clustering.

Questions Answered: How concentrated are passing or excellent contracts?

Inputs: Security-level opportunity counts and scan totals.

Outputs: Planned concentration index value.

Owns: Concentration metric definition.

Does NOT Own: Ranking, scoring, or trading decisions.

Relationships: Derived from Opportunity Concentration.

Module(s): Planned

Status: Emerging

### Opportunity Diversity Index (ODI)

Definition: A planned metric describing how broadly opportunities are distributed across the universe.

Purpose: Quantify diversity of opportunity sources.

Questions Answered: How diverse is the opportunity set?

Inputs: Security-level opportunity distribution.

Outputs: Planned diversity index value.

Owns: Diversity metric definition.

Does NOT Own: Universe construction or model thresholds.

Relationships: Complements OCI.

Module(s): Planned

Status: Emerging

### Historical Repository

Definition: The accumulated body of persisted scan evidence.

Purpose: Enable longitudinal research from repeated observations.

Questions Answered: What has been observed over time? What scan evidence exists for a research question?

Inputs: Archived Opportunity Scans and linked rows.

Outputs: Historical datasets for research analysis.

Owns: Persistent empirical evidence.

Does NOT Own: Interpretations, hypotheses, or conclusions.

Relationships: Implemented by the SQLite Research Repository.

Module(s): `data/research/opportunity_scans.sqlite`, `src/research_repository.py`

Status: Stable

### Research Notebook

Definition: The permanent research journal for observations, hypotheses, experiments, conclusions, and questions.

Purpose: Preserve research reasoning over time.

Questions Answered: What has been observed? What is believed, uncertain, or planned for research?

Inputs: Scan evidence, diagnostic review, researcher interpretation.

Outputs: Observation log, hypothesis log, major findings.

Owns: Research narrative and accumulated interpretation.

Does NOT Own: Raw scan evidence or application behavior.

Relationships: References Study Protocols, Observations, Hypotheses, and Experiments.

Module(s): `docs/research/Research_Notebook.md`

Status: Stable

### Study Protocol

Definition: A repeatable observational study definition with purpose, configuration, and schedule context.

Purpose: Make repeated scans comparable.

Questions Answered: Why is this scan being run? Which configuration should it use? How should it be repeated?

Inputs: Evaluation Profile, Reference Universe, option type, DTE range, purpose, suggested schedule.

Outputs: Study metadata persisted with Opportunity Scans.

Owns: Repeatable study configuration and purpose.

Does NOT Own: Model logic, scoring thresholds, scan outcomes.

Relationships: Associated with Opportunity Scans and Research Notebook entries.

Module(s): `src/study_protocol.py`, `research_scan.py`

Status: Stable

### Research Session

Definition: A focused period of research activity, review, or experimentation.

Purpose: Group related observations and decisions.

Questions Answered: What work was performed in this research period? Which scans or documents were reviewed?

Inputs: Research goals, scan IDs, notebook entries, analysis outputs.

Outputs: Session notes and possible observations or hypotheses.

Owns: Research activity context.

Does NOT Own: Persistent scan storage or model behavior.

Relationships: May produce Observations, Interpretations, Hypotheses, or Experiments.

Module(s): Documentation concept

Status: Emerging

### Observation

Definition: A recorded empirical statement supported by evidence.

Purpose: Capture what has been seen without over-claiming causality.

Questions Answered: What did the evidence show?

Inputs: Scan evidence, diagnostics, repository summaries.

Outputs: Observation log entries.

Owns: Evidence-backed statements.

Does NOT Own: Speculation, model changes, conclusions beyond evidence.

Relationships: Can support or conflict with Hypotheses.

Module(s): `docs/research/Research_Notebook.md`

Status: Stable

### Interpretation

Definition: A reasoned explanation of what observations may mean.

Purpose: Bridge observations and hypotheses while preserving uncertainty.

Questions Answered: What might this observation imply?

Inputs: Observations, domain knowledge, historical context.

Outputs: Research notes and candidate hypotheses.

Owns: Explicitly qualified reasoning.

Does NOT Own: Empirical facts or validated conclusions.

Relationships: May lead to Hypotheses.

Module(s): Documentation concept

Status: Emerging

### Hypothesis

Definition: A testable research claim derived from observations and interpretations.

Purpose: Direct future research toward evidence-producing experiments.

Questions Answered: What claim should be tested?

Inputs: Observations, interpretations, conflicting evidence.

Outputs: Hypothesis log entries and planned experiments.

Owns: Testable claims and current status.

Does NOT Own: Model changes before testing.

Relationships: Tested by Experiments and updated by evidence.

Module(s): `docs/research/Research_Notebook.md`

Status: Stable

### Experiment

Definition: A planned or completed research procedure designed to test a hypothesis.

Purpose: Produce evidence that supports, weakens, or refines a hypothesis.

Questions Answered: What was tested? How was it tested? What evidence resulted?

Inputs: Hypothesis, Study Protocol, scan data, analysis method.

Outputs: Results, observations, conclusions, follow-up questions.

Owns: Research procedure and result context.

Does NOT Own: Production behavior or model changes unless separately approved.

Relationships: Uses Study Protocols and Historical Repository data.

Module(s): Documentation concept

Status: Emerging

---

## 4. System Entities

### SQLite Research Repository

Definition: The local SQLite database that stores archived Opportunity Scans and linked research rows.

Purpose: Persist empirical evidence outside the UI runtime.

Questions Answered: Where are completed scans stored? Which rows belong to a scan?

Inputs: Scan metadata, evaluated contract export rows, rule evaluation rows, security characterization rows.

Outputs: Queryable historical scan data.

Owns: Database schema and persistence mechanics.

Does NOT Own: Research conclusions, charts, or model behavior.

Relationships: Implements the Historical Repository.

Module(s): `src/research_repository.py`, `data/research/opportunity_scans.sqlite`

Status: Stable

### Export Bundle

Definition: A set of structured exports that preserve scan data and diagnostics.

Purpose: Allow offline validation and research review.

Questions Answered: What data can be exported from a scan? Can rule outcomes be replayed or audited?

Inputs: Evaluated rows, rule evaluations, QED summaries.

Outputs: CSV and JSON artifacts.

Owns: Export shape and field naming.

Does NOT Own: Persistence, scoring rules, or research conclusions.

Relationships: Feeds external analysis and repository archival paths.

Module(s): `app.py`

Status: Stable

### Instrumentation

Definition: Structured capture of internal model and scan outputs for research use.

Purpose: Make model behavior observable and auditable.

Questions Answered: What did the model evaluate? Which rules fired? What context surrounded the scan?

Inputs: CQM outputs, scan metadata, profile metadata.

Outputs: Export rows, repository records, diagnostics.

Owns: Measurement and capture points.

Does NOT Own: Model decisions or research interpretation.

Relationships: Supports QED, Research Repository, and Study Protocols.

Module(s): `app.py`, `src/research_repository.py`, `src/quality_diagnostics.py`

Status: Stable

### Scan Metadata

Definition: Context fields attached to an Opportunity Scan.

Purpose: Make persisted scans interpretable and comparable.

Questions Answered: When did this scan run? Which profile, universe, DTE range, option type, and study protocol were used?

Inputs: Runtime scan context, Evaluation Profile metadata, Study Protocol metadata.

Outputs: Metadata columns in `opportunity_scans` and export rows.

Owns: Scan context identity fields.

Does NOT Own: Evaluated contract data or rule results.

Relationships: Links Opportunity Scans to profiles and protocols.

Module(s): `src/research_repository.py`, `src/evaluation_profile.py`, `src/study_protocol.py`

Status: Stable

### Security Passport (planned)

Definition: A planned persistent profile summarizing a security's observed behavior across scans.

Purpose: Characterize recurring security behavior over time.

Questions Answered: What is this security usually like under the active Evaluation Profile?

Inputs: Historical Security Characterization rows, scan metadata, rule summaries.

Outputs: Planned security-level research profile.

Owns: Longitudinal security behavior summary.

Does NOT Own: Trade recommendations or security selection rules.

Relationships: Builds on Historical Repository and Security Characterization.

Module(s): Planned

Status: Emerging

### Outcome Tracking (planned)

Definition: Planned capture of forward results after a scan.

Purpose: Support outcome research and attribution.

Questions Answered: What happened after this opportunity was observed?

Inputs: Scan candidates, future market data, contract or underlying security prices.

Outputs: Outcome records and attribution inputs.

Owns: Forward-looking evidence capture.

Does NOT Own: Predictions, live trading, or order execution.

Relationships: Enables Outcome Attribution and model performance characterization.

Module(s): Planned

Status: Emerging

### Architecture Decision Record (ADR)

Definition: A formal record of a significant architectural decision.

Purpose: Preserve why major design choices were made.

Questions Answered: What was decided? Why? What alternatives were considered?

Inputs: Decision context, options, consequences.

Outputs: ADR document.

Owns: Architectural rationale.

Does NOT Own: Research observations or implementation details unrelated to the decision.

Relationships: Complements the glossary, roadmap, and research notebook.

Module(s): Planned documentation

Status: Emerging

---

## 5. Entity Relationships

Platform

-> Evaluation Profiles

-> Reference Universes

-> Securities

-> Option Contracts

-> Opportunity Discovery

-> Contract Quality Model

-> Quick Evaluation

-> Opportunity Scans

-> Scan Metadata

-> SQLite Research Repository

-> Historical Repository

-> Security Characterization

-> Rule Characterization

-> Near Miss Analysis

-> Opportunity Concentration

-> Research Notebook

-> Observations

-> Interpretations

-> Hypotheses

-> Experiments

-> Future Outcome Tracking

Evaluation Profiles orchestrate analytical models. Reference Universes define the population being evaluated. Opportunity Discovery executes the scan. The Contract Quality Model evaluates contracts. QED explains one scan. The SQLite Research Repository stores evidence. The Research Notebook records what is observed, interpreted, hypothesized, and tested.

---

## 6. Terminology Evolution

| Previous Name | Current Name | Reason for the Change |
| --- | --- | --- |
| Watchlist | Reference Universe | "Watchlist" implied an informal list, while "Reference Universe" defines a stable research population. |
| Scoring Algorithm | Contract Quality Model | The logic is a model of contract quality, not merely a numeric scoring routine. |
| Scanner | Opportunity Discovery | The workflow discovers and ranks observed opportunities rather than performing generic scanning. |
| Quality Score | Contract Quality Model score | Clarifies that the score belongs to contract-level quality evaluation. |
| Dashboard Diagnostics | Quick Evaluation (QED) | Names the single-scan diagnostic layer as a research artifact. |
| Scan Results | Opportunity Scan | Treats one completed run as a persistent research entity. |
| Research Database | SQLite Research Repository | Clarifies both implementation and architectural role. |
| Ticker Summary | Security Characterization | Clarifies that ticker-level summaries are research characterizations of securities. |

---

## 7. Guiding Principles

- Characterize before optimizing.
- Separate Security evaluation from Contract evaluation.
- Evaluation Profiles orchestrate analytical models.
- Reference Universes define populations.
- Research requires persistent evidence.
- Observations precede hypotheses.
- Hypotheses precede model changes.
- A scan is evidence, not a conclusion.
- Model changes require accumulated evidence and explicit rationale.
- Diagnostics should explain model behavior without silently changing it.
- Research artifacts should preserve uncertainty where evidence is incomplete.

---

## 8. Future Entities

### Outcome Attribution

Planned analysis that connects later outcomes to earlier observed opportunity, security, contract, and market-context features.

### Market Regime

Planned classification of broader market conditions that may contextualize scan behavior.

### Forward Outcome Tracking

Planned capture of future price, contract, and underlying-security behavior after a scan.

### Paper Portfolio Simulation

Potential research-only simulation layer for studying how model-selected candidates would behave under explicit hypothetical rules.

### Behavior Classification

Planned grouping of securities or contracts by recurring observed behavior.

### Market Context

Planned capture of broad market, sector, volatility, and liquidity context at scan time.

### Technical Indicator Repository

Planned storage of technical indicators used by future security-level analytical models.
