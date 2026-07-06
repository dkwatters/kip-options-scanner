# Architectural Principles

## Purpose

These principles guide the Kip Options quantitative research platform as it evolves from a local scanner into a cloud-hosted research system.

They are intended to protect interpretability, research discipline, and operational boundaries. They apply to documentation, model design, repository design, cloud execution, and future feature work.

---

## 1. Separate Discovery, Evaluation, Characterization, and Research

The platform keeps research responsibilities distinct:

- Discovery builds or observes a population.
- Security Research characterizes underlying securities through the Security Analysis Model.
- Opportunity Research discovers option opportunities and evaluates them through the Option Analysis Model.
- Research Universe Definition specifies, generates, and snapshots the population being studied.
- Metadata records descriptive context about repositories, protocols, scans, and execution state.
- Research interprets accumulated evidence through notebook entries, hypotheses, protocols, and reports.

No layer should silently take over another layer's responsibility.

---

## 2. Research Universes Are First-Class

A Research Universe is the population boundary for a study. Results are interpretable only when the observed population is explicit.

The platform should distinguish:

- Market Universe: what could be studied.
- Research Universe: the central workflow object that defines what is in scope for a specific study.
- Research Universe Definition: the reusable specification for manual, predefined, or generated universes.
- Static Research Universe: explicit membership from a curated list, file, or predefined dataset.
- Dynamic Research Universe: membership produced from documented criteria and source data.
- Research Universe Generator: future functionality for creating or refreshing universes from selection criteria.
- Research Universe Snapshot: point-in-time membership used by an observation.

Population construction should remain separate from Opportunity Discovery and OAM scoring. Downstream workflows should not care whether a universe was manually defined, predefined, or generated; they should consume the selected Research Universe and its snapshot.

Research Universe Snapshots protect reproducibility. A scan, Study Protocol observation, or research run should be interpretable against the exact securities that were in scope at observation time.

---

## 3. Opportunity Discovery Is Observation, Not Recommendation

Opportunity Discovery identifies visible passing and near-miss candidates under the active configuration. It does not recommend trades, predict outcomes, place orders, or imply suitability.

Its output is research evidence.

---

## 4. OAM Owns Option Analysis Only

The Option Analysis Model owns option-level quality rules, thresholds, margins, and scores.

OAM does not own:

- Research Universe membership.
- Security Analysis Model state.
- Outcome attribution.
- Portfolio decisions.
- Study conclusions.

Changes to OAM behavior require explicit research rationale and should not be introduced through unrelated metadata, navigation, or UI work.

---

## 5. SAM Is Independent Security Research

The Security Analysis Model records security-level technical condition at scan time.

SAM must not change OAM scoring, Opportunity Discovery filtering, rankings, OAE diagnostics, Evaluation Profile behavior, or Study Protocol execution unless a future research decision explicitly promotes SAM outputs into another evaluated model.

---

## 6. The Research Repository Stores Evidence, Not Meaning

The Research Repository persists observations and linked data. It should make evidence durable, queryable, and comparable across local and cloud execution.

Interpretation belongs in the Research Notebook, reports, or explicit analysis artifacts.

---

## 7. Study Protocols Protect Comparability

Repeated observations should be tied to Study Protocols when they are intended to support longitudinal research.

Scheduled Observations and Exploratory Observations must remain distinguishable so protocol progress is not contaminated by ad hoc scans.

---

## 8. Cloud Execution Preserves Domain Boundaries

Cloud infrastructure changes where the platform runs, not what the platform means.

Render Cron Jobs execute scheduled observations. Render Web Service presents the dashboard. Render Postgres stores research evidence. Browser sessions inspect evidence. None of these infrastructure components should alter OAM, SAM, Opportunity Discovery semantics, or Study Protocol rules by deployment side effect.

---

## 9. Prefer Explicit Versioning and Rationale

Evaluation Profiles, Study Protocols, model versions, and major terminology shifts should be named and recorded.

Research changes should explain:

- What changed.
- Why it changed.
- Which evidence motivated the change.
- Which behavior remains unchanged.

---

## 10. Characterize Before Optimizing

The platform should first describe observed behavior, then form hypotheses, then test those hypotheses, and only then consider model changes.

Premature optimization weakens research quality because it can erase the evidence needed to understand why a model behaves as it does.

---

## 11. Documentation Is Part of the Architecture

Architecture documents, glossary entries, diagrams, cloud notes, and research notebook entries are part of the system's control surface.

When terminology or responsibilities change, documentation should be updated alongside the conceptual change so future implementation work has a stable target.
