# Universe Interpretation Presentation Contract v0.1

## Purpose and position

This contract is the renderer-neutral deterministic layout boundary between `InterpretationSelectionResultV01` and future Streamlit, API, export, Current Read, What Changed, or Morning Coffee renderers. It maps selected references into bounded sections and slots without discovering facts or generating prose.

## Input and output

The sole primary input is the selection result. The versioned output contains presentation metadata, seven ordered sections, bounded slots, compact presentation items, display label keys and scalar values, evidence references, and explicit overflow accounting. It does not read snapshots, raw market data, repositories, or providers.

## Sections, roles, and mappings

The contract preserves `current_read`, `deserves_attention`, `what_changed`, `leaders`, `laggards`, `membership_changes`, and `caveats` order. Current Read maps its first non-caveat to `primary_fact`, later facts to `supporting_fact`, and comparison limitations to `caveat`. Attention candidates map to `member_card`; changes to `change_card`; leaders/laggards to their row roles; additions/removals to distinct membership roles; caveats to `caveat`.

Renderer-neutral label keys include `attention_candidate`, `change_event_type`, `leader_position`, `laggard_position`, `member_added`, `member_removed`, and `caveat_code`. Values are bounded scalar identifiers, source positions, reason codes, or member/event references. No locale formatting or sentences are produced.

## Limits and overflow

`InterpretationPresentationPolicyV01` versions per-section capacity plus Current Read primary/caveat role capacity. Presentation can only narrow the selected set. Every omitted source is recorded in source order with selected, presented, and omitted counts and `presentation_capacity_exceeded`; no item is silently dropped.

## Ordering, identity, and traceability

Section order is fixed. Slot order preserves selection order after deterministic capacity filtering. UUIDv5 contract, section, slot, and item IDs cover the source snapshot/policy/section/role/index/selected identity. Every item traces to exactly one selected item and preserves source type, source identity, member/event references, reason, priority, and sorted unique evidence.

One selected source appears at most once per section. Cross-section reuse is neither created nor removed; it follows the selection result. Validation rejects unknown sections, roles, sources, versions, duplicate IDs/sources, invalid ordering, capacity violations, overflow errors, lost evidence, or identity changes.

## Comparison safety and determinism

Not-comparable results cannot contain What Changed slots. Limited and full comparisons map only facts already selected. Repeated execution produces identical immutable contracts and JSON-safe serialization.

## Intentionally excluded and future consumers

No narrative, recommendation, sentiment, interpretation, AI/provider call, database/network I/O, metric/rank/priority calculation, UI behavior, or Morning Coffee behavior is implemented. Future renderers may map label keys and scalar values into governed human-facing output without changing this factual layout contract.
