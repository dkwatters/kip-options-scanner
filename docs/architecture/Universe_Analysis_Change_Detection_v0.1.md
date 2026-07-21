# Universe Analysis Change Detection v0.1

## Purpose and boundary

This pure domain service converts two persisted `UniverseAnalysisSnapshotV1` artifacts plus a successful `SnapshotComparisonAssessmentV01` into deterministic, auditable atomic events and company groups. It does not independently reassess comparability.

There is no prose interpretation yet, no AI or provider call, no Morning Coffee, no UI, and no analytical scoring change.

## Contracts and rule version

`UniverseChangeEventV01` (`universe_change_event.v0.1`) records universe/snapshot/subject identity, previous and current values, direction, materiality, rule provenance, timestamps, evidence references, deterministic status and confidence. `UniverseChangeGroupV01` preserves every atomic event ID for one universe/member/comparison interval. `UniverseChangeDetectionResultV01` records status, assessment, events, groups, suppressions, counts and detection time.

Change behavior alone is versioned by `universe-change-rules-v0.1`.

## Comparability dependency

Not-comparable assessments produce a typed `not_comparable` result and no events. Limited assessments permit only their explicit categories and technical fields. Full assessments permit all v0.1 fields. Rank is a hard opt-in through `rank_comparison_allowed`. Extension requires compatible presentation and extension-threshold versions.

## Transition rules

- Profiles use `Strong > Constructive > Mixed > Weak` only to classify direction. Every transition is notable; a transition of two or more levels is attention.
- Trend uses an explicit matrix for known transitions. Entry to or exit from bullish/bearish alignment is attention; unknown label pairs are `changed`.
- Momentum orders only negative/neutral/positive. Extension-risk states use explicit pairs: positive to overbought-positive is `changed`, not improved; mixed overbought/oversold transitions are not flattened.
- Extension is positioning evidence: near-trend to moderately-extended is changed; moderately-extended to elevated is deteriorated; elevated to near-trend and below-long-term-trend to near-trend are improved. Elevated transitions are attention.
- Volatility low/moderate/high changes describe risk context. A two-level change is attention. Numeric changes within one regime are suppressed.
- Price/SMA and SMA/SMA states use the persisted below/near/above and bearish/neutral/bullish labels. 200-day and 50/200 transitions are attention; 50-day is ahead of 20-day and 20/50 in ordering.
- Rank requires unchanged population identity and denominator. Material movement is `abs(delta) >= max(2, ceil(analyzed_population * 0.20))`. Top-three boundary events require six members; top-quartile boundary events require eight. Lower rank numbers mean improved relative position only.

## Availability, membership, and noise

Analyzed to unavailable emits a separate `availability_lost`; restored analysis emits `availability_restored`. Neither implies technical direction. Added and removed members emit membership events with entered/exited direction and preserve both universe versions. Unavailable in both snapshots emits nothing.

RSI, MACD, price, raw SMA, within-regime realized volatility, within-profile technical-score movement, and sub-threshold rank movement never emit standalone v0.1 events. They remain snapshot evidence.

## Identity, evidence, grouping, and priority

Event UUIDv5 identity covers both snapshot IDs, rule, subject, field and both values. Group UUIDv5 identity covers the interval and subject. Stable sorting makes repeated results equivalent.

Technical events link baseline and current snapshot/member/field plus the persisted evidence ID. Availability and membership link their member ledger/membership location in each snapshot.

Priority is presentation metadata, not an investment score: coverage caveats; profile; long-term trend/200-day/50-200; momentum; extension; volatility; qualifying rank; short-term 20-day/20-50. A group with multiple consistently directed technical events may move one presentation tier earlier without changing any event, technical score, or rank.
