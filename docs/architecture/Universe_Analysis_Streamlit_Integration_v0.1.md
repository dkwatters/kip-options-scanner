# Universe Analysis Streamlit Integration v0.1

## User journey and purpose

The product journey remains Home → Research Launchpad → Research Universe → Analyze Universe → Universe Analysis. After exact-universe execution, the Universe Analysis page is the primary destination for current rankings, member detail, and the deterministic intelligence sections Current Read, What Deserves Attention, What Changed, Leaders, Laggards, Membership Changes, Caveats, and Snapshot/Comparison Context.

## Deterministic pipeline and orchestration

`build_universe_analysis_presentation()` is the narrow application boundary. Given the active persisted snapshot ID and snapshot repository, it loads the current artifact, inspects older history for the same universe, prefers the newest fully comparable baseline, then limited, then explicit not-comparable, and invokes the existing comparison → change detection → interpretation input → selection → presentation pipeline. It performs no market-data work, scoring, provider access, or prose generation.

The first persisted snapshot returns an explicit `first_snapshot` outcome without manufacturing a comparison. A missing current artifact returns a typed unavailable outcome. Assembly exceptions remain visible while the completed current analysis continues to render.

## Renderer adapter and sections

The pure Streamlit adapter iterates the Presentation Contract’s section and slot order. It joins each presentation item’s exact selected/member/event identity to bounded source fields for human-readable cards and rows. It never introduces an item absent from the presentation contract, reranks members, changes priority, or restores suppressed events.

Current Read uses the presentation primary/supporting roles. Attention, leader, and laggard rows may activate the existing member detail state. What Changed displays exact before/after values, rule-produced direction, interval, priority, and evidence count. Additions/removals remain membership facts. Caveats are always visible notices. Overflow counts remain visible.

## Labels, safety, and empty states

A small Streamlit-specific dictionary resolves only label keys emitted by Presentation Contract v0.1. Unknown stable keys fall back to a mechanical title; label resolution never changes values. First-run, no snapshot, assembly failure, no-change, unavailable-member, limited, and not-comparable states are explicit. Comparison safety is inherited from the contracts and is not reevaluated in UI code.

## Traceability and exclusions

Snapshot/Comparison Context exposes universe/version, observation interval, comparison classification, current/baseline snapshot IDs, analysis run ID, and unavailable count. Existing raw technical diagnostics remain secondary.

This integration adds no AI narrative, Morning Coffee, provider call, indicator, chart, recommendation, candidate-generation, scoring, Study Protocol, scheduled-scan, retention, or cloud-job behavior. A future Morning Coffee renderer can consume the same Presentation Contract. A future Technical Observation Engine can enrich upstream deterministic facts without changing this renderer boundary.
