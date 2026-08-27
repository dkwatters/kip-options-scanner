# POE-B003 — Typed Signal & Outcome Families v0.2

## Evidence intent

This document identifies the longitudinal evidence to preserve for the v0.2 architecture release. It is not a new frozen benchmark corpus. Frozen POE-B001 and the completed POE-B002 Signal integration evidence remain unchanged.

## Implementation brief and decisions

Preserve the implementation brief titled “Typed Signal & Outcome Families v0.2,” the implementation commits, and `docs/architecture/Typed_Signal_Outcome_Families_v0.2.md`.

The principal decision is that analytical family is independent from direction. Directional Signals retain v0.1 meaning. Volatility Signals use the explicit `not_applicable` direction because nullable direction would require reconstruction of the v0.1 SQLite table. `neutral` and `abstain` were explicitly rejected as representations for a non-directional model.

The release adds only `directional`/`volatility` Signal families and `return`/`volatility` Outcome families. Additional families, top-level volatility fields, real volatility outcomes, and production smoke-Signal generation were rejected as premature scope.

## Evidence chain

Preserve:

- additive SQLite and Postgres bootstrap SQL;
- legacy-row compatibility tests;
- family validation and immutable round-trip tests;
- explicit Signal-to-Outcome routing tests;
- unchanged Technical Setup identity/version/semantics tests;
- Model Lab family isolation tests;
- Universe Analysis, Opportunity Discovery, technical scan, and full-suite regression results;
- review findings and corrective commits;
- manual acceptance results, if performed;
- final before/after behavior and residual risks;
- explicitly deferred v0.3+ functionality.

## Before and after

- Before: every Signal was implicitly directional and every outcome implicitly a forward return.
- After: persisted records carry explicit families, while legacy records deterministically resolve to `directional` and `return`.
- Before: a non-directional observation had no honest direction representation.
- After: volatility Signals use `not_applicable` and cannot enter directional distributions or hit-rate denominators.

No v0.1 Signal is migrated to a different meaning, and no future volatility performance statistic is fabricated.
