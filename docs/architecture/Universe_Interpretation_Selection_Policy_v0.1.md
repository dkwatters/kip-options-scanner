# Universe Interpretation Selection Policy v0.1

## Purpose and position

The selection policy is a deterministic editorial eligibility layer between `UniverseInterpretationInputV01` and future presentation or interpretation consumers. It selects references to facts already in the case file. It does not discover facts, calculate analysis, or generate prose.

## Input, output, and versioning

The only primary input is `UniverseInterpretationInputV01`. `InterpretationSelectionPolicyV01` fixes section limits, the maximum eligible existing change-priority tier, and duplicate/reuse behavior under `universe-interpretation-selection-policy-v0.1`. `InterpretationSelectionResultV01` contains seven ordered `InterpretationSelectionSectionV01` sections with bounded `InterpretationSelectedItemV01` references. Selected items preserve source identity, member/event identity, original priority, evidence, reason code, and deterministic ordering metadata.

## Sections and eligibility

- `current_read`: highest existing attention candidates, explicit comparison limitations, then the first already-ranked leader and laggard.
- `deserves_attention`: existing attention candidates in their contractual priority order, including unavailable members.
- `what_changed`: existing priority events within the configured tier, suppressed completely for not-comparable intervals and empty for no-change intervals.
- `leaders` and `laggards`: existing case-file sequences, bounded without reranking.
- `membership_changes`: existing additions followed by removals; membership is not interpreted technically.
- `caveats`: existing caveat codes only.

Limited comparisons use only events that survived comparison and change detection. Not-comparable intervals retain current-state sections and caveats but never select interval change events.

## Reasons, ordering, and duplicates

Stable reasons include high-priority change, current attention candidate, current leader/laggard, membership addition/removal, explicit caveat, and comparison limitation. Ordering uses existing priority tier, existing source/rank order, stable matching key, and source ID. UUIDv5 selected-item IDs include snapshot, section, type, and source.

The same exact source cannot repeat within a section. Exact sources selected in earlier strong sections are suppressed from later strong sections. Current Read is explicitly allowed to reuse a conceptual member through its distinct attention/leader/laggard source role; member reuse across semantic sections is therefore allowed, while an event is never duplicated inside What Changed. Evidence is sorted and deduplicated.

## Validation and guarantees

Validation rejects unsupported policy versions, negative limits, unknown sections/source types, missing source references, duplicate identities, limit violations, invalid ordering/evidence, and unsafe not-comparable change selection. Execution is pure, repeatable, JSON-safe, and performs no I/O.

## Exclusions and future consumers

The policy adds no prose, sentiment, recommendation, opinion, AI/provider access, database/network access, metric/rank/scoring calculation, UI, Morning Coffee, or protected research behavior. Future Current Read, What Changed, audit, and Morning Coffee layers may consume the bounded result under separate governance.
