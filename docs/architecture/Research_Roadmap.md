# Quantitative Research Platform Architecture

## Purpose

This document describes the current architecture and research direction of the Kip Options quantitative research platform.

The platform has evolved from a local stock/options screener into a cloud-capable quantitative research system for repeated observation, security analysis, opportunity analysis, and evidence accumulation. It is not a trading system, recommendation engine, broker integration, or order-routing service.

---

## Architectural Frame

The core architecture separates five responsibilities:

- Universe Definition: select, generate, version, and snapshot defined study populations.
- Security Research: characterize underlying securities.
- Opportunity Research: discover and evaluate option opportunities over a Research Universe.
- Metadata: persist descriptive context about repositories, protocols, scans, and execution state.
- Research: accumulate evidence through repeatable protocols and notebook interpretation.

This separation keeps model behavior interpretable. Universe Definition can run without making research conclusions. Evaluation can produce contract-quality evidence without claiming predictive power. Characterization can describe market state without changing rankings. Research can reason over accumulated evidence without mutating production behavior.

---

## Core Domain Concepts

### Market Universe

The Market Universe is the broad set of securities that could theoretically be observed by the platform. It is larger than any one study and may include equities, ETFs, sectors, or future market populations not yet active in a protocol.

The Market Universe is a conceptual boundary, not the current execution input. It answers: what could be studied?

### Research Universe

A Research Universe is the central workflow object of the research platform: a named, explicit study population selected from the Market Universe for a research purpose. It replaces the older "watchlist", "Corpus", and "Reference Universe" terminology as the first-class population concept.

A Research Universe answers:

- Which securities are in scope for this study or scan?
- Why were these securities selected?
- Which population should results be interpreted against?

A Research Universe may be static or dynamic. Static universes are predefined from manual or curated membership. Dynamic universes are produced by a generator from documented criteria. Downstream workflows should not care how the universe was created; they should consume the resulting Research Universe Definition or Research Universe Snapshot.

### Research Universe Definition

A Research Universe Definition is the reusable specification for a Research Universe. It records the name, purpose, selection method, criteria, source data, ownership notes, and expected refresh behavior.

Manual and predefined CSV-backed universes are valid Research Universe Definitions. Generated universes are also valid Research Universe Definitions when their generator and criteria are documented.

### Static Research Universe

A Static Research Universe has explicit membership supplied by a manual list, curated file, or predefined dataset. Current CSV-backed universe files are implementation artifacts for Static Research Universe Definitions.

### Dynamic Research Universe

A Dynamic Research Universe is produced or refreshed from selection criteria, source data, and a repeatable generation process. It may change membership across refreshes, but each run should produce a snapshot for reproducibility.

### Research Universe Generator

A Research Universe Generator creates or refreshes Research Universe Definitions and snapshots from manual lists, technical criteria, fundamental criteria, news, sentiment, or other future population-construction inputs.

It does not evaluate option contracts and does not change OAM thresholds. Its role is population construction, not opportunity scoring. "Security Discovery" is an older or broader name for this future population-construction responsibility.

### Research Universe Snapshot

A Research Universe Snapshot is the point-in-time membership of a Research Universe used by a scan, Study Protocol observation, or research run. It preserves reproducibility by recording exactly which securities were in scope for that observation, regardless of whether membership came from a static list or a dynamic generator.

### Opportunity Discovery

Opportunity Discovery executes scans over a Research Universe. It retrieves market data, evaluates option chains, applies option analysis, and selects visible passing or near-miss candidates for review.

Opportunity Discovery currently operates against manually defined CSV-backed Research Universes. It owns orchestration and candidate presentation. It does not own OAM rule definitions, SAM characterization, research conclusions, or future outcome claims.

### Option Analysis Model

The Option Analysis Model (OAM), historically called the Contract Quality Model (CQM), evaluates option contracts using option-level rules such as delta fit, spread, open interest, volume, and score components.

OAM answers: is this option contract structurally acceptable under the active rules?

It remains independent from security-level analysis and does not consume SAM values for filtering, scoring, ranking, or threshold changes.

### Security Analysis Model

The Security Analysis Model (SAM), historically called the Technical Analysis Model (TAM), records underlying-security technical context at scan time. Current indicators include price, moving-average relationships, RSI, MACD, realized volatility, and derived state labels when data supports them.

SAM answers: what technical condition was observable for the underlying security at the time of the scan?

SAM is the current Security Research model. It does not modify Opportunity Discovery, OAM scoring, OAE diagnostics, Evaluation Profile behavior, or Study Protocol execution.

The Security Setup Score shown in the Security Analysis Explorer (SAE), historically the Technical Analysis Explorer (TAE), is Experimental / Observational. It summarizes SAM observations for visual review only. It does not define Research Universe gates and does not influence option scoring, Opportunity Discovery, OAM, OAE, rankings, filters, thresholds, or Evaluation Profile logic.

The current SAM field definitions, calculations, decision trees, limitations, and future evolution notes are documented in `docs/research/Technical_Analysis_Model_Specification.md`, whose file name preserves the historical TAM terminology.

### Security Analysis Explorer

The Security Analysis Explorer (SAE), historically called the Technical Analysis Explorer (TAE), is the analytical workspace for inspecting SAM observations, summary distributions, technical states, visual setup scores, and QA tables.

SAE is observational. It does not change Opportunity Discovery, OAM scoring, Research Universe membership, Study Protocol execution, or repository behavior.

### Option Analysis Explorer

The Option Analysis Explorer (OAE), historically called Quality Engine Diagnostics (QED), is the analytical workspace for inspecting OAM score distributions, rule evaluations, pass and near-miss behavior, diagnostics, and option-analysis evidence.

OAE explains option-analysis behavior after OAM evaluation. It does not define Research Universe membership, SAM calculations, OAM thresholds, rankings, or Study Protocol rules.

### Research Repository

The Research Repository persists completed observations and linked evidence. Local development uses SQLite. Cloud deployment uses Postgres through the repository backend configuration.

The repository stores empirical evidence, not interpretations. It supports archived Opportunity Scans, evaluated contracts, rule evaluations, security characterization, technical characterization, Study Protocol context, and protocol progress.

### Study Protocol

A Study Protocol defines repeatable observational research: purpose, Research Universe, Evaluation Profile, option type, DTE range, run mode expectations, and schedule labels.

Study Protocols separate planned evidence from exploratory scans. Scheduled observations count toward protocol progress only when archived with the appropriate run mode and scheduled time label.

---

## Logical Domain Model

```mermaid
flowchart TD
    MU[Market Universe] --> RUD[Research Universe Definition]
    ML[Manual / Predefined Universes] --> RUD
    RUG[Research Universe Generator] --> RUD
    RUD --> RUS[Research Universe Snapshot]
    RUS --> RU[Research Universe]
    RU --> SP[Study Protocol]
    EP[Evaluation Profile] --> SP
    SP --> OD[Opportunity Discovery]
    RU --> OD
    RU --> SAM[Security Analysis Model]
    SAM --> SAE[Security Analysis Explorer]
    OD --> OAM[Option Analysis Model]
    OAM --> OAE[Option Analysis Explorer]
    OAM --> EV[Evaluated Contracts and Rule Evaluations]
    SAM --> TC[Security Characterization]
    OD --> OS[Opportunity Scan]
    OS --> RR[Research Repository]
    EV --> RR
    TC --> RR
    RR --> RMS[Research Metadata Sidebar]
    RR --> RN[Research Notebook]
    RD --> RN
```

Key relationship rules:

- A Market Universe contains securities that could be studied.
- A Research Universe is the central study population selected from the Market Universe.
- A Research Universe Definition documents how the universe is specified, whether manually, predefined, or generated.
- A Static Research Universe has explicit curated membership.
- A Dynamic Research Universe is generated from criteria and source data.
- A Research Universe Generator creates or refreshes Research Universe Definitions and snapshots; current Research Universes are manually defined CSV files.
- A Research Universe Snapshot preserves the exact point-in-time membership used by an observation.
- A Study Protocol binds research purpose, population, schedule, and execution context.
- Opportunity Discovery observes the Research Universe at a point in time.
- OAM evaluates option contracts.
- SAM characterizes underlying securities.
- The Research Repository stores evidence.
- The Research Notebook records observations, hypotheses, rationale, and conclusions.

---

## Research Workflow

The canonical research workflow is:

Market Universe -> Research Universe Definition -> Research Universe Snapshot -> Security Analysis Model / Security Analysis Explorer -> Opportunity Discovery -> Option Analysis Model / Option Analysis Explorer -> Research Repository / Study Protocols

In practice, the user selects a Research Universe. That universe may be static, such as a manual or predefined CSV-backed list, or dynamically generated from documented criteria. Once selected, the Research Universe Snapshot preserves the exact securities used for the observation so later analysis remains reproducible.

SAM characterizes the securities in the selected universe, and SAE provides analytical exploration of those security-level observations. Opportunity Discovery then finds visible option opportunities from that same universe. OAM evaluates the option contracts, and OAE provides analytical exploration of model behavior, scores, rules, pass outcomes, and near misses. The Research Repository stores the resulting evidence, while Study Protocols make repeated observations comparable and repeatable.

Downstream workflows should not depend on whether a Research Universe came from a manual list, a predefined file, or a generator. They should operate against the selected Research Universe and its snapshot.

---

## Cloud Deployment Architecture

```mermaid
flowchart LR
    GH[GitHub Repository] --> RWS[Render Web Service]
    GH --> RCJ[Render Cron Jobs]
    RWS --> PG[(Render Postgres)]
    RCJ --> PG
    PG --> RWS
    B[Browser] --> RWS
```

Deployment responsibilities:

- GitHub stores application, runner, and documentation source.
- Render Web Service hosts the Streamlit research dashboard.
- Render Cron Jobs execute scheduled Study Protocol observations.
- Render Postgres is the cloud Research Repository.
- Browser sessions inspect dashboard views backed by the cloud repository.

Cloud execution preserves the same domain boundaries as local execution. Cron jobs create observations; they do not reinterpret research evidence. The web service presents and inspects evidence; it does not replace scheduled execution.

---

## Current Architecture State

### Complete or Substantially Complete

- Evaluation Profiles.
- CSV-backed Static Research Universe Definitions, historically Reference Universes.
- Opportunity Discovery.
- Option Analysis Model, historically Contract Quality Model.
- SQLite Research Repository.
- Postgres Research Repository backend for cloud use.
- Study Protocols.
- Export instrumentation.
- Scheduled Observation execution.
- Research metadata sidebar protocol progress.
- Security Analysis Model v0.1.
- Security Analysis Explorer v0.1.
- Security Setup Score v0.1 as an Experimental / Observational Explorer display field.
- TAM-001 Daily Technical Characterization protocol and TAM-only runner.
- Research sidebar organization with separate Opportunity Research and Security Research metadata sections.

### Active Evolution

- Cloud-hosted dashboard and scheduled observations on Render.
- Repository abstraction between local SQLite and cloud Postgres.
- Research Universe terminology and first-class documentation.
- Research Universe Definition and Snapshot terminology.
- Technical characterization as an independent research layer.

### Planned Research Capabilities

- Research Universe Generator implementation.
- Security Characterization expansion.
- Excellent Contract Characterization.
- Rule Characterization expansion.
- Near Miss Characterization.
- Opportunity Concentration and Diversity metrics.
- Security Passports.
- Outcome Tracking.
- Market Context capture.
- Market Regime characterization.
- Versioned research reports.

---

## Roadmap

### Phase 1 - Research Foundation

Status: Complete / Substantially Complete

- Evaluation Profiles.
- Research Universes.
- Opportunity Discovery.
- Option Analysis Model.
- Local Research Repository.
- Study Protocols.
- Export instrumentation.
- Scheduled observation execution.
- Research metadata sidebar protocol progress.

### Phase 2 - Cloud Continuous Observation Infrastructure

Status: Active

- Render Web Service for the dashboard.
- Render Cron Jobs for scheduled research scans.
- Render Postgres as the cloud Research Repository.
- Repository backend configuration.
- Cloud startup checks and environment validation.

### Phase 3 - Research Characterization

Status: Emerging

- Security Analysis Model v0.1 security-level observations.
- Security Analysis Explorer v0.1 QA and observation view.
- Security Setup Score v0.1 visual summary.
- Security Analysis Model Functional Specification v1.0.
- TAM-001 historical observation protocol for daily technical-only scans.
- Security Characterization.
- Excellent Contract Characterization.
- Rule Characterization.
- Near Miss Characterization.
- Opportunity Concentration.
- Security Passports.

SAM remains a research-only layer. It persists underlying-security technical observations but does not filter, score, rank, or otherwise change Option Analysis Model or Opportunity Discovery behavior.

TAM-001 is the historical protocol identifier for SAM-only observations. The `technical_scan.py` runner writes only `technical_characterization` rows and does not run Opportunity Discovery, fetch option chains, evaluate contracts, produce OAM rows, or change OAE, Evaluation Profile, ranking, or threshold behavior.

### Phase 4 - Longitudinal Research

Status: Planned

- Trend Analysis.
- Security Behavior Classification.
- Evaluation Profile Health.
- Rule Stability.
- Opportunity Diversity Index.
- Opportunity Concentration Index.
- Model Drift Detection.

### Phase 5 - Outcome Research

Status: Planned

- Forward Outcome Tracking.
- Underlying Security Tracking.
- Contract Tracking.
- Market Context Capture.
- Outcome Attribution.

### Phase 6 - Scientific Evaluation

Status: Planned

- Hypothesis Testing.
- Evaluation Profile Comparison.
- Option Analysis Model Comparison.
- Versioned Research Reports.
- Model Performance Characterization.

---

## Guiding Statement

The objective of the platform is not to predict markets. The objective is to characterize, measure, and improve analytical models through disciplined observation and accumulated evidence.
