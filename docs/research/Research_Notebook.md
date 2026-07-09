# Research Notebook

## Purpose

This notebook captures empirical observations and model research over time for the Kip Options quantitative research platform.

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

### Milestone M4 - Security Analysis Model v0.1 Added

Date: 2026-07-06

Definition:
The first independent stock-level technical research layer was added as Security Analysis Model v0.1, historically called Technical Analysis Model v0.1.

Evidence:

- Technical observations archive to `technical_characterization`.
- Initial indicators include price, 20/50/200-day SMA relationships, RSI 14, MACD, and 20-day realized volatility when price history supports it.
- SAM rows are linked to Opportunity Scans by `scan_id` when generated during scans.
- SAM remains research metadata and does not alter OAM scoring, Opportunity Discovery ranking, OAE, thresholds, or Evaluation Profile behavior.

Status:
Complete

---

### Milestone M5 - Security Analysis Explorer v0.1 Added

Date: 2026-07-06

Definition:
A read-only Security Analysis Explorer was added to visualize and QA SAM output.

Evidence:

- The explorer reads existing rows from `technical_characterization`.
- It shows latest SAM observations, filters by ticker, state, latest scan, and optional `scan_id`, and surfaces summary cards plus QA distributions.
- The explorer is observational only and does not alter options filtering, ranking, OAM scoring, OAE, thresholds, or Evaluation Profile behavior.

Status:
Complete

---

### Milestone M6 - Research Universe Architecture Adopted

Date: 2026-07-06

Definition:
The platform architecture and research vocabulary were reframed around Market Universes, Research Universes, Research Universe generation, Opportunity Discovery, independent evaluation models, and persistent research evidence.

Evidence:

- Research Universe is now the preferred first-class term for the active study population.
- Market Universe describes the broader population from which Research Universes may be selected.
- Research Universe Generator is identified as the population-construction responsibility, separate from Opportunity Discovery and OAM.
- Opportunity Discovery remains the scan workflow that observes a Research Universe and surfaces visible passing or near-miss candidates.
- OAM remains contract-level evaluation only.
- SAM remains independent security-level research metadata.
- Research Repository and Study Protocols remain the persistence and repeatability anchors for accumulated evidence.

Rationale:
The prior stock-screener framing was too narrow for a cloud-hosted research platform that now supports scheduled observations, repository-backed evidence, technical characterization, and protocol progress. Treating Research Universes as first-class makes every scan interpretable against an explicit population boundary and prevents population construction from being conflated with contract evaluation or opportunity ranking.

Status:
Complete

---

### Milestone M7 - Security Analysis Explorer Visual Indicators v0.1 Added

Date: 2026-07-06

Definition:
The Security Analysis Explorer added derived visual state indicators and an Experimental / Observational Technical Setup Score for easier scan review.

Evidence:

- Derived display states summarize price versus 20/50/200 SMAs, 20/50 and 50/200 SMA alignment, MACD state, and RSI regime.
- Raw numeric SAM fields remain visible beside the derived states.
- The Technical Setup Score summarizes trend alignment, MACD momentum, RSI regime, and volatility state on a 0-100 scale.
- The v0.1 rubric is 40 points for trend alignment, 25 for MACD momentum, 20 for RSI regime, and 15 for volatility. Score grade bands are Strong technical setup, Constructive, Neutral / mixed, Weak, and Poor.
- The score is descriptive, unvalidated, and display-only. It does not define Research Universe gates.
- The score does not influence Opportunity Discovery, OAM scoring, OAE, option rankings, filters, thresholds, Evaluation Profile behavior, or Study Protocol execution.

Status:
Complete

---

### Milestone M8 - Security Analysis Model Functional Specification v1.0 Added

Date: 2026-07-06

Definition:
The Security Analysis Model received a dedicated functional specification documenting its responsibilities, inputs, outputs, calculations, state decision trees, limitations, and future evolution paths.

Evidence:

- `docs/research/Technical_Analysis_Model_Specification.md` defines current SAM v0.1 behavior while preserving the historical filename.
- The specification distinguishes SAM from Opportunity Discovery, OAM, Evaluation Profiles, Study Protocols, and future Research Universe Generators.
- The specification documents persisted SAM fields, Explorer-derived display fields, Technical Setup Score, Technical Setup Grade, and Technical Notes.
- The sprint was documentation-only and did not change executable behavior.

Status:
Complete

---

### Milestone M9 - SAM Historical Observation Protocol v0.1 Added

Date: 2026-07-06

Definition:
An independent SAM-only observation protocol was added for daily stock-level technical characterization without Opportunity Discovery or option-contract evaluation.

Evidence:

- `technical_scan.py` runs SAM-only observations over `data/technology_growth_ai_v1.csv`.
- TAM-001 metadata identifies the Daily Technical Characterization protocol and preserves the historical protocol identifier.
- Scheduled SAM-only runs are intended for `16:30 ET` and skip weekends and U.S. equity market holidays through `market_calendar`.
- SAM-only persistence writes `technical_characterization` rows with study and run metadata.
- The runner does not fetch option chains, run OAM, create evaluated contract rows, create rule evaluation rows, or alter OD/OAE/Evaluation Profile behavior.

Status:
Complete

---

### Milestone M10 - Research Sidebar Refactoring v1.0 Added

Date: 2026-07-06

Definition:
The left sidebar was reorganized to reflect the platform research architecture by separating contract-level research context from security-level technical research context.

Evidence:

- Startup Check and Tradier Connection remain top-level sidebar sections.
- The prior Research Dashboard sidebar area is now an expandable Research section.
- Contract Research contains Study Protocol, Evaluation Profile, Research Universe, repository, latest Opportunity Discovery observation, protocol progress, and scan history views.
- Security Research contains SAM observation summary widgets including latest technical observation, securities characterized, average SAM score, trend/momentum/volatility distributions, SAM errors, and technical study status.
- The sprint changed sidebar organization only and did not change OD, OAM, SAM calculations, Study Protocol execution, Evaluation Profiles, OAE, scoring, rankings, repository behavior, or infrastructure.

Status:
Complete

---

### Milestone M11 - Information Architecture and Domain Model Refactoring v2.0 Added

Date: 2026-07-06

Definition:
The application information architecture was reframed around Market Universe, Research Universe, Security Research, and Opportunity Research.

Evidence:

- The sidebar now keeps Research metadata separate from analytical explorers.
- The Research sidebar initially presents Security Research and Opportunity Research choices only.
- Security Research sidebar metadata covers latest security observation, latest scan timestamp, securities characterized, repository status, Security Study Protocol status, latest study identifier, run mode, version, error count, and technical characterization counts.
- Opportunity Research sidebar metadata covers latest opportunity observation, Study Protocol execution, scheduled observation progress, repository status, run mode, manual versus scheduled mode, scan identifier, and observation counts.
- The main workspace now groups Security Analysis Explorer (SAE) under Security Research and Opportunity Discovery, Option Chain Explorer, and Option Analysis Explorer (OAE) under Opportunity Research.
- Current terminology identifies Security Analysis Model (SAM), Security Analysis Explorer (SAE), Option Analysis Model (OAM), and Option Analysis Explorer (OAE). Historical names are documented as TAM, TAE, CQM, and QED.
- Research Universe Generator is documented as future population-construction functionality. Opportunity Discovery currently operates on manually defined CSV-backed Research Universes.
- The sprint changed information architecture, navigation, UI terminology, and documentation only. It did not change Opportunity Discovery behavior, SAM calculations, OAM calculations, scoring algorithms, thresholds, Evaluation Profiles, Study Protocol execution, repository schema, OAE analytical behavior, or cloud infrastructure.

Status:
Complete

---

### Milestone M12 - Research Universe Workflow Architecture Finalized

Date: 2026-07-06

Definition:
The research information architecture was finalized around Research Universe as the central workflow object and clarified the distinction between Research Universe Definitions, static and dynamic universes, Research Universe Generators, and Research Universe Snapshots.

Evidence:

- The canonical flow is Market Universe -> Research Universe Definition -> Research Universe Snapshot -> Security Analysis Model / Security Analysis Explorer -> Opportunity Discovery -> Option Analysis Model / Option Analysis Explorer -> Research Repository / Study Protocols.
- Manual and predefined universes are valid Research Universe Definitions.
- Generated universes are valid Research Universe Definitions when their generator criteria and source data are documented.
- Downstream workflows should consume the selected Research Universe and snapshot without depending on whether the universe was manually curated, predefined, or generated.
- Research Universe Snapshots preserve reproducibility by fixing the exact securities observed by a scan, protocol observation, or research run.
- User-facing terminology is Security Analysis Model (SAM), Security Analysis Explorer (SAE), Option Analysis Model (OAM), and Option Analysis Explorer (OAE). Historical terms remain TAM, TAE, CQM, and QED where needed for code names, file names, protocol identifiers, or historical notes.
- The sprint changed documentation and terminology alignment only. It did not change Opportunity Discovery behavior, SAM calculations, OAM calculations, scoring algorithms, thresholds, Evaluation Profiles, Study Protocol execution, repository schema, repository behavior, OAE analytical behavior, cloud infrastructure, or executable behavior.

Status:
Complete

---

### Milestone M13 - Research Universe Design Specification v0.1 Added

Date: 2026-07-06

Definition:
The platform added a documentation-only Research Universe Design Specification v0.1 before implementation.

Evidence:

- `docs/architecture/Research_Universe_Design_Specification.md` defines Market Universe, Research Universe Definition, Research Universe Snapshot, Research Universe Generator, and Research Universe Gate as first-class concepts.
- Static and dynamic universes are specified to become identical to downstream workflows after snapshot creation.
- Opportunity Discovery is specified to consume a Research Universe Snapshot rather than a mutable definition directly.
- SAM may provide gate input fields to a future generator, but SAM remains independent security-level characterization and does not become the generator.
- Research Universe Generators are specified as population-construction components only; they do not evaluate option contracts and do not modify OD, OAM, SAM, OAE, SAE, Evaluation Profile, Study Protocol, database, cloud job, or UI behavior.
- The implementation plan is phased as RU-1 static definitions and snapshots, RU-2 management UI, RU-3 bounded dynamic generation using existing SAM fields, and RU-4 user-defined gates.
- The sprint changed documentation only.

Rationale:
Dynamic universe generation creates reproducibility, cost, rate-limit, and responsibility-boundary risks if it is implemented before the architecture is explicit. The snapshot-first design lets CSV universes, manual watchlists, index universes, and future generated universes all become the same downstream input while preserving exact observed membership.

Status:
Complete

---

### Milestone M14 - Product Vision and Experience Architecture v1.0 Added

Date: 2026-07-07

Definition:
The platform added a non-technical product vision and experience architecture document that sits above the technical architecture, domain glossary, model specifications, and PRDs.

Evidence:

- `docs/product/Product_Vision_and_Experience_Architecture.md` defines the platform as a configurable investment research platform that translates a user's question, thesis, or mission into a repeatable research workflow.
- The document establishes Research Mission and Research Strategy as product-level concepts that precede Research Universe selection, Security Research, Opportunity Research, and historical observation.
- The experience model defines four sophistication levels: Curious Beginner, Growing Investor, Experienced Investor / Trader, and Research Power User.
- The research journey is described as User Question / Mission -> Research Strategy -> Research Universe -> Security Research -> Opportunity Research -> Historical Observation -> Confidence / Decision.
- The document reinforces progressive disclosure: questions before data, research before recommendations, ideas before indicators, repeatable observations before opinions, and complexity revealed only when useful.
- The sprint changed documentation only and did not change executable behavior, Opportunity Discovery, Security Analysis Model, Option Analysis Model, Study Protocols, repository behavior, cloud infrastructure, scoring, thresholds, or tests.

Rationale:
The technical architecture already defines platform components and responsibility boundaries, but the product needed a higher-level experience frame that starts with user intent. This milestone clarifies that future UX should begin with "What are you trying to accomplish today?" or "What are we researching?" rather than defaulting into a scanner, chart, or preselected universe.

Status:
Complete

---

### Milestone M15 - Research Conversation Engine Workflow Design v0.1 Added

Date: 2026-07-07

Definition:
The platform added a documentation-only Research Conversation Engine workflow design for translating a user's research question into a user-reviewed Research Universe Definition.

Evidence:

- RCE is defined as the upstream workflow that translates a Research Mission into structured research artifacts.
- The documented workflow is User Question -> RCE Structured Interpretation -> Candidate Universe Proposal -> User Review/Edit/Name -> Research Universe Definition -> Research Universe Snapshot -> SAM/SAE -> OD/OAM/OAE -> Research Repository.
- AI-Assisted Research Universe Definition, Candidate Security, Inclusion Rationale, User-Approved Research Universe, and Research Universe Snapshot are defined as reviewable artifact concepts.
- The UX proposal starts from a Research Workspace landing page with mission input, proposed universe preview, edit/name/save controls, and handoff to Security Research or Opportunity Research.
- User stories were added for Curious Beginner, Growing Investor, Experienced Investor / Trader, and Research Power User.
- The sprint changed documentation only and did not change executable behavior, scoring, OD, SAM, OAM, Evaluation Profiles, Study Protocols, cloud jobs, or database schema.

Rationale:
RCE is valuable only if it keeps the product conversational without weakening research boundaries. The user should be able to start with a plain-language question, but no AI-assisted universe should proceed into analysis until the user reviews and approves the Research Universe Definition.

Status:
Complete

---

### Milestone M16 - Research Question Taxonomy and Conversation Design v0.1 Added

Date: 2026-07-08

Definition:
The platform added a documentation-only Research Question Taxonomy and Research Conversation Engine design specification for classifying natural-language research questions and translating them into reviewable research artifacts.

Evidence:

- `docs/product/Research_Question_Taxonomy_and_Conversation_Design.md` defines RQT as a taxonomy of research intent, not a list of canned questions.
- The documented flow is Natural-language user question -> Research Question Taxonomy classification -> Research Intent Profile -> Research Conversation Engine -> Research Mission -> Research Strategy -> Research Universe Definition -> Research Universe Snapshot -> Security Research / Opportunity Research.
- RQT domains include Discover, Evaluate, Opportunity Research, Compare, Learn, Validate, Monitor, and Build.
- Research lenses include Technical, Fundamental, Options, Income, Risk, Valuation, Competitive Position, Event-Driven, Macro Exposure, and Theme / Narrative.
- The specification defines Research Intent Profile fields, confidence handling, persona-aware conversation, representative scenarios, and future prompt template needs.
- The sprint changed documentation only and did not change executable behavior, database schema, scoring, Opportunity Discovery, Security Analysis Model, Option Analysis Model, Study Protocols, cloud infrastructure, repository behavior, or UI behavior.

Rationale:
RCE needs an explicit intent-classification layer before it proposes missions, strategies, universes, or downstream paths. RQT makes broad, ambiguous, beginner, trader, and power-user questions interpretable without turning the platform into a recommendation engine or bypassing user review.

Status:
Complete

---

### Milestone M17 - Research Workspace RQT/RCE Landing Page v0.1 Added

Date: 2026-07-08

Definition:
The Research Workspace landing page was refactored to reflect the Research Question Taxonomy and Research Conversation Engine direction without adding AI integration or analytical behavior.

Evidence:

- The landing page now asks "What are we researching?" and captures a plain-language research question.
- Starting-point cards cover Explore an investment theme, Research a company, Build or refine a watchlist, Find option opportunities, Compare prior research, and Learn a concept.
- Entering a question shows a Research Conversation Preview describing the eventual RCE steps: interpret the question, identify intent, suggest a path, propose a Research Mission, suggest or create a Research Universe, and require user review before analysis begins.
- The page states that the current version captures the research question but does not yet generate a universe automatically.
- Continue Previous Research surfaces CSV-backed Research Universes and recent observations when available.
- Advanced Research provides shortcuts to Security Research, Opportunity Research, and the Research Repository.

Rationale:
The product experience should begin with user intent while preserving the current analytical boundaries. This landing page makes the future RQT/RCE workflow visible without pretending that classification, AI-assisted universe generation, or approval persistence has been implemented.

Status:
Complete

---

### Milestone M18 - Research Workspace Conversation-Forward UX v0.4

Date: 2026-07-08

Definition:
The Research Workspace landing page was simplified so the experience begins with the user's curiosity and uses research-domain suggestion cards as coaching rails.

Evidence:

- The hero now centers on "Every investment begins with curiosity" and asks "What can I help you understand today?"
- The question box is the primary action, with a single Start Conversation button.
- Four coaching cards cover Explore an Investment Idea, Research a Company, Find Investment Opportunities, and Compare & Learn.
- Card selection prefills the question box, stores the selected research path, and shows a placeholder preview without navigation, AI calls, universe generation, or analysis.
- The preview explains that future RCE behavior will interpret, clarify, suggest a research path, propose a Research Mission, suggest or create a Research Universe, and require review before analysis begins.
- Advanced users can still jump to Security Research, Opportunity Research, or the Research Repository.

Rationale:
Conversation is the front porch for research, not a chatbot wrapper. The landing page should capture the user's question first, then allow guidance and deterministic evidence workflows to follow. Conversation starts the process. Evidence completes it.

Status:
Complete

---

### Milestone M19 - Product Vision and Research Experience Alignment v1.0

Date: 2026-07-08

Definition:
The product documentation was aligned around the evolution from a traditional stock/options screener into a question-driven research platform.

Evidence:

- Product philosophy now states that the platform begins with curiosity rather than tickers, conversation starts the process, evidence completes it, and the application remembers research rather than conversations.
- The product journey is documented as Question -> Research Conversation -> Research Guidance -> Research Mission -> Research Universe -> Security Analysis -> Opportunity Discovery -> Findings -> Research Refinement.
- Research Conversation Engine boundaries were tightened: RCE exists only to understand intent, clarify when necessary, define a Research Mission, and propose a Research Universe.
- Research Guidance is documented as persistent contextual support, distinct from the brief Research Conversation.
- Research Session is documented as a first-class product concept preserving Original Question, Research Mission, Research Universe, Findings, Refinements, Decisions, and Saved Notes.
- Research Refinement is documented as structured modification of existing research rather than continuation of an AI chat.
- Beginner-first natural-language entry is documented while preserving direct access for experienced users.
- The sprint changed documentation only and did not change executable behavior, scoring, Opportunity Discovery, Security Analysis Model, Option Analysis Model, Study Protocols, cloud jobs, repository behavior, or tests.

Rationale:
The platform needs a durable product memory model that preserves research artifacts and evidence instead of treating conversation as the primary object. Conversation should help users get started, especially beginners, but analytical models and repository-backed evidence remain the source of research findings.

Status:
Complete

---

## Observation Log

### Observation 001

Observation ID: OBS-001

Date: 2026-07-01

Study Protocol: SP-001 Intraday Technology Growth AI Calls

Observation: Model architecture separated Security evaluation from Contract evaluation.

Evidence: The current research workflow distinguishes Universe and Evaluation Profile context from the Option Analysis Model, and archives evaluated option contracts separately from ticker-level security characterization.

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

Evidence: SAM rows persist separately in `technical_characterization`, while contract-level rows and rule evaluations continue to be archived through the existing OAM path.

Confidence: High

Follow-up Questions: Do specific SAM states correlate with later option quality, opportunity persistence, or forward outcomes across repeated scans?

### Observation 007

Observation ID: OBS-007

Date: 2026-07-06

Study Protocol: Platform Architecture

Observation: Research Universes need to be treated as first-class research entities rather than incidental scan inputs.

Evidence: Scheduled observations, cloud repository storage, Study Protocol progress, SAM characterization, and future outcome research all depend on knowing the population being observed. Without an explicit Research Universe boundary, scan results can be misread as market-wide behavior or as behavior of an informal watchlist.

Confidence: High

Follow-up Questions: What criteria should the first Research Universe Generator use, and how should generated universe versions be recorded for reproducible studies?

### Observation 008

Observation ID: OBS-008

Date: 2026-07-06

Study Protocol: Platform Architecture

Observation: Research Universe Snapshot is required to make static and dynamically generated universes equally reproducible downstream.

Evidence: A manual CSV-backed universe and a future generated universe can both serve as valid Research Universe Definitions, but repeated observations need the exact point-in-time membership to compare SAM characterization, Opportunity Discovery output, OAM behavior, and Study Protocol progress.

Confidence: High

Follow-up Questions: Should explicit Research Universe Snapshot persistence be added to the Research Repository, or is scan-time membership sufficient until dynamic generators are implemented?

### Observation 009

Observation ID: OBS-009

Date: 2026-07-06

Study Protocol: Platform Architecture

Observation: Research Universe generation should begin from bounded candidate lists rather than the entire market.

Evidence: Provider rate limits, latency, symbol coverage, optionable-status discovery, and data freshness risks become material when attempting broad market enumeration. Bounded lists such as existing curated CSV universes, S&P 500, Nasdaq 100, or manually curated optionable lists make generation testable without adding option-chain retrieval or changing OD/OAM behavior.

Confidence: High

Follow-up Questions: Which bounded candidate list should be the first RU-3 generator input, and what provider metadata should be stored with each generated snapshot?

### Observation 010

Observation ID: OBS-010

Date: 2026-07-06

Study Protocol: Platform Architecture

Observation: SAM can support dynamic Research Universe generation without becoming responsible for universe membership.

Evidence: SAM already records security-level technical fields that are plausible gate inputs, including RSI, MACD state, moving-average relationships, trend state, and realized volatility. A Research Universe Generator can read those fields under an explicit Research Universe Definition while SAM remains an observational model and OD/OAM behavior remains unchanged.

Confidence: High

Follow-up Questions: Which SAM fields are stable enough for initial gates, and should gate pass/fail evidence be persisted per snapshot member in RU-3 or deferred until RU-4?

---

### Observation 011

Observation ID: OBS-011

Date: 2026-07-07

Study Protocol: Platform Architecture

Observation: RCE should be treated as an intent-translation workflow rather than a scoring, discovery, or recommendation layer.

Evidence: The RCE design requires user review/edit/name before saving a Research Universe Definition. Candidate Securities and Inclusion Rationale explain research scope only, while SAM, SAE, OD, OAM, OAE, Evaluation Profiles, Study Protocols, cloud jobs, and repository schema remain unchanged.

Confidence: High

Follow-up Questions: What is the minimal persistence model needed to preserve RCE interpretation, user edits, approval metadata, and inclusion rationale without coupling RCE to model outputs?

---

### Observation 012

Observation ID: OBS-012

Date: 2026-07-08

Study Protocol: Platform Architecture

Observation: RQT should classify research intent before RCE proposes missions, strategies, universes, or downstream analysis paths.

Evidence: The RQT/RCE design separates intent domains, research lenses, Research Intent Profile fields, interpretation confidence, clarification handling, persona-aware conversation, and candidate universe proposal into distinct responsibilities. This keeps RCE upstream of SAM, OD, OAM, Study Protocols, repository behavior, and research conclusions.

Confidence: High

Follow-up Questions: Which fields in the Research Intent Profile should be persisted first when RCE implementation begins, and which should remain transient conversation context?

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
