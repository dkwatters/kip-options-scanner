# Universe Interpretation Input Contract v0.1

## Purpose

`UniverseInterpretationInputV01` is the deterministic case file supplied to future interpretation consumers. It aggregates already-established snapshot, comparison, and change-detection facts without explaining, recommending, scoring, or generating prose.

## Architecture and inputs

The pure builder accepts a baseline `UniverseAnalysisSnapshotV1`, current `UniverseAnalysisSnapshotV1`, their `SnapshotComparisonAssessmentV01`, and matching `UniverseChangeDetectionResultV01`. It validates that every artifact references the same comparison interval and that stable identities and event identities are unique.

The current snapshot is the authoritative source for current Universe Analysis metadata, summary, leaders, laggards, availability, and member evidence. The comparison assessment supplies membership sets and caveats. The change result supplies deterministic counts, events, groups, priorities, and event evidence.

## Contract layout

- `metadata`: universe, snapshot interval, timing, freshness, and behavior versions.
- `universe_summary`: the existing immutable current snapshot summary.
- `comparison_summary`: the existing typed assessment.
- `change_summary`: existing deterministic event counts.
- `priority_events`: bounded events ordered by their existing deterministic priority metadata.
- `leaders` and `laggards`: current analyzed members ordered by persisted rank; ranks are not recalculated.
- `additions` and `removals`: assessment identities resolved to current or baseline member facts.
- `attention_candidates`: change groups plus currently unavailable members, with machine-readable reasons.
- `caveats`: sorted reason/suppression/freshness codes.
- `evidence_refs`: deduplicated snapshot, member, and event evidence identifiers.

Unavailable values remain `null`, and empty sections remain empty tuples/lists after serialization. Missing information is not replaced with interpretive defaults.

## Deterministic guarantees

Contracts are frozen and slot-backed. Ordering uses persisted rank, priority metadata, membership order, and stable matching keys with explicit tie-breakers. Evidence is deduplicated and sorted. `to_dict()` produces a JSON-safe structure. The builder performs no I/O, provider calls, state mutation, technical calculation, rank recalculation, or scoring.

## Future consumers

Potential consumers include a deterministic Current Read selector, a separately governed interpretation service, audit exports, and Morning Coffee. Every consumer receives the same bounded facts and provenance.

## Intentionally excluded

This sprint adds no AI, prose interpretation, recommendations, opinions, Morning Coffee behavior, UI, alerts, provider access, change-event rules, comparison rules, technical classification, or production scoring changes.
