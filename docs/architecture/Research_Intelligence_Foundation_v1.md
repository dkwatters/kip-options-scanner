# Research Intelligence Foundation v1

## Purpose

The Research Intelligence Foundation is the deterministic architecture that turns an approved research universe into immutable analysis history, auditable changes, bounded interpretation inputs, editorial selections, and renderer-neutral presentation structures. It establishes a strict boundary between facts and explanation so that every future consumer receives the same traceable evidence.

Its governing rule is simple:

> Facts are established deterministically. Interpretation consumes facts. Rendering consumes interpretation. AI never establishes truth; AI may only explain validated facts.

## Core design principles

- **Deterministic truth:** universe membership, technical observations, derived states, comparison eligibility, changes, selection, and layout are produced by versioned rules.
- **Immutable history:** snapshots preserve what was known at a point in time and are never recalculated during comparison.
- **Explicit compatibility:** historical artifacts are compared only after a typed assessment authorizes the relevant categories.
- **Atomic auditability:** changes remain individual rule-provenanced events with stable identities and evidence links.
- **Layered responsibility:** each layer accepts typed outputs from the layer before it and does not reach around the pipeline for hidden inputs.
- **Bounded consumption:** interpretation and presentation contracts limit, order, and reference facts without inventing new ones.
- **Stable provenance:** deterministic identifiers and evidence references survive from observations through presentation slots.
- **AI isolation:** providers and language models are absent from the factual pipeline. A future narrative layer may explain its output but cannot change it.
- **Consumer neutrality:** the foundation does not privilege Streamlit, an API, Markdown, PDF, or Morning Coffee.

## Architecture

```text
Research Universe
        │
        ▼
Universe Analysis
        │
        ▼
Snapshot Contract
        │
        ▼
Snapshot Persistence
        │
        ▼
Snapshot Comparison
        │
        ▼
Deterministic Change Detection
        │
        ▼
Interpretation Input Contract
        │
        ▼
Interpretation Selection Policy
        │
        ▼
Interpretation Presentation Contract
        │
        ▼
Renderer Adapter (future)
        │
        ├───────────────┐
        ▼               ▼
Streamlit UI     Morning Coffee
        │               │
        ├───────┬───────┤
        ▼       ▼       ▼
REST API   Markdown   PDF
```

The arrows represent typed data flow, not permission to reinterpret upstream facts. Later layers may narrow or arrange earlier outputs; they may not silently recalculate or override them.

## Architectural layers

### Research Universe

**Purpose:** Define the approved research population and its question, identity, ordering, and provenance.

**Inputs:** Curated or validated research-universe requests and resolved member identities.

**Outputs:** An ordered, versioned universe handoff with stable matching keys, analyzable constituents, unresolved members, and provenance references.

**Responsibilities:** Preserve universe identity and version; distinguish membership from analyzability; provide deterministic member ordering; carry the research question and provenance into analysis.

**Explicit non-responsibilities:** It does not calculate technical states, rank companies, compare history, generate changes, recommend securities, or produce narrative interpretation.

### Universe Analysis

**Purpose:** Execute the existing deterministic technical characterization over the exact approved universe.

**Inputs:** Research Universe handoff, technical observations, and established analysis/scoring behavior versions.

**Outputs:** Reconciled analysis rows, derived technical presentation states, relative ranks, universe summary counts, and an execution ledger including unavailable members.

**Responsibilities:** Apply current technical classification and ranking semantics consistently; reconcile requested, analyzed, unavailable, and unresolved members; preserve raw and derived evidence.

**Explicit non-responsibilities:** It does not alter universe membership, infer company events, compare snapshots, interpret changes, or generate user-facing research conclusions. The history foundation does not change its scoring semantics.

### Snapshot Contract

**Purpose:** Capture one completed Universe Analysis run as an immutable, versioned point-in-time artifact.

**Inputs:** The exact Research Universe handoff, reconciled analysis run, technical rows, version manifest, and timing/provenance metadata.

**Outputs:** `UniverseAnalysisSnapshotV1`, containing universe and run identity, ordered members, raw and derived observations, ranks and denominators, summary, freshness, evidence, and behavior versions.

**Responsibilities:** Enforce reconciliation invariants; preserve analyzed and unavailable membership; make observations traceable; serialize deterministically; record the versions required for future compatibility decisions.

**Explicit non-responsibilities:** It does not persist itself, select a baseline, compare history, emit changes, recalculate analysis, or contain prose.

### Snapshot Persistence

**Purpose:** Durably store and retrieve validated snapshots without changing their contents.

**Inputs:** A validated `UniverseAnalysisSnapshotV1`.

**Outputs:** Reproducible snapshot storage and retrieval by ID and universe history, with SQLite and PostgreSQL repository seams.

**Responsibilities:** Store canonical payloads transactionally; prevent conflicting writes for one snapshot ID; reconstruct typed contracts; expose ordered history; integrate narrowly after a completed analysis run.

**Explicit non-responsibilities:** It does not derive missing data, mutate historical snapshots, compare records, persist change events, or decide which snapshot is analytically meaningful.

### Snapshot Comparison

**Purpose:** Decide whether two persisted snapshots may safely be compared and which comparison categories are allowed.

**Inputs:** Baseline and current `UniverseAnalysisSnapshotV1` artifacts.

**Outputs:** A versioned `SnapshotComparisonAssessmentV01` declaring full, limited, or no comparability; stable, added, and removed identities; permitted technical fields/categories; rank eligibility; and reason codes.

**Responsibilities:** Evaluate universe identity, membership, analyzed population, schema and behavior versions, and presentation compatibility; make rank eligibility an explicit invariant; identify the stable intersection.

**Explicit non-responsibilities:** It does not emit change events, recalculate ranks, fuzzy-match names, reinterpret technical labels, or generate prose. Downstream services must honor rather than repeat its decision.

### Deterministic Change Detection

**Purpose:** Emit auditable atomic events for meaningful changes expressly allowed by the comparison assessment.

**Inputs:** Baseline snapshot, current snapshot, and their exact comparison assessment.

**Outputs:** Versioned change events, deterministic company groups, priority metadata, counts, suppressions, evidence links, and a typed detection status.

**Responsibilities:** Apply explicit transition matrices for profile, trend, momentum, extension, volatility, moving-average state, rank, availability, and membership; suppress numeric noise; preserve every atomic event; assign UUIDv5 identities and rule provenance.

**Explicit non-responsibilities:** It does not create investment scores, recalculate technical analysis, infer recommendations, collapse events into prose, call providers, or persist an interpretation of what happened.

### Interpretation Input Contract

**Purpose:** Assemble the deterministic case file that any future interpretation consumer must use.

**Inputs:** Baseline/current snapshots, comparison assessment, and matching change-detection result.

**Outputs:** `UniverseInterpretationInputV01` with current metadata and summary, change counts and events, leaders, laggards, additions, removals, attention candidates, caveat codes, and deduplicated evidence references.

**Responsibilities:** Validate that all artifacts describe one interval; reuse existing typed facts; order members and events deterministically; represent unavailable information explicitly; preserve provenance.

**Explicit non-responsibilities:** It does not explain facts, select editorial content, generate opinions, recalculate ranks, access providers, or render output.

### Interpretation Selection Policy

**Purpose:** Decide which case-file facts are eligible for future presentation and in which semantic section.

**Inputs:** `UniverseInterpretationInputV01` only.

**Outputs:** `InterpretationSelectionResultV01` with bounded selected references for Current Read, Deserves Attention, What Changed, Leaders, Laggards, Membership Changes, and Caveats.

**Responsibilities:** Enforce versioned section limits, allowed source types, comparison safety, reason codes, deterministic tie-breaking, duplicate suppression, and documented cross-section reuse.

**Explicit non-responsibilities:** It does not discover facts, rerank members, alter event priority, infer sentiment, write summaries, access raw observations, or call AI.

### Interpretation Presentation Contract

**Purpose:** Map editorial selections into a renderer-neutral deterministic layout.

**Inputs:** `InterpretationSelectionResultV01` only.

**Outputs:** `InterpretationPresentationContractV01` with metadata, ordered sections, bounded slots, compact source-traceable items, display label keys and scalar values, stable IDs, and explicit overflow diagnostics.

**Responsibilities:** Preserve selection order and identities; assign display roles such as primary fact, member card, change card, leader/laggard row, membership addition/removal, and caveat; enforce section and role capacity; validate evidence and source traceability; serialize consistently.

**Explicit non-responsibilities:** It does not create labels as sentences, enrich selections from snapshots, reprioritize, format for locale, implement UI, generate narrative, or contact a provider.

## Future renderer layer

**Purpose:** Resolve renderer-neutral roles, label keys, and scalar values into a specific output medium under an explicit adapter contract.

**Inputs:** A validated Interpretation Presentation Contract, plus a versioned label/catalog resource appropriate to the medium and locale.

**Outputs:** UI components, API payloads, Markdown, PDF structures, or other channel-specific artifacts.

**Responsibilities:** Honor section/slot order, overflow, evidence, accessibility, escaping, and medium constraints; keep source identities available for diagnostics and audit.

**Explicit non-responsibilities:** A renderer must not query raw data to add facts, change selection, recalculate analysis, or override comparison safety.

### Future Morning Coffee

Morning Coffee may schedule and distribute a renderer-specific view of validated presentation contracts. It should consume the same deterministic artifacts as every other channel, clearly distinguish unavailable/no-comparison states, and preserve evidence/audit identity. It must not become an alternate analysis engine or a privileged source of truth.

### Future API

An API may serialize contracts directly or expose a renderer-adapted schema. It should version responses, preserve deterministic IDs and reason codes, enforce authorization, and avoid leaking provider credentials or internal runtime state. It must not construct unvalidated changes on demand.

### Future Streamlit UI

Streamlit may render sections and slots using approved components and label keys. UI state may choose what the user expands or navigates to, but must not alter factual eligibility, ordering, ranks, priorities, or comparison status.

### Future PDF and Markdown export

Export adapters may paginate, wrap, link evidence, and include deterministic overflow appendices. They must preserve source order and values, avoid locale-dependent analytical changes, and never fill missing facts with invented content.

### Future AI narrative

AI is optional and downstream of deterministic presentation. If introduced, it may translate selected, validated facts into governed explanatory language. Its complete input must be bounded by the contracts, its output must remain traceable to source items, and it must not add unsupported facts, recommendations, scores, causal claims, or hidden provider knowledge.

AI never establishes truth. It may only explain validated facts. Any narrative is a rendering of the deterministic record, not a replacement for it.

## Maintenance guidance

Changes should occur in the earliest layer that owns the responsibility and should carry a dedicated behavior or schema version. A renderer request must not leak backward into technical scoring; a new change rule must not be hidden inside selection; a new editorial preference must not alter snapshots. Tests should verify deterministic replay, immutable inputs, evidence preservation, comparison safety, stable ordering, and protected subsystem behavior at every boundary.

The foundation is complete when a future consumer can move from an approved universe to a traceable presentation contract without AI, prose, UI, or external interpretation. That is the baseline this document records.
