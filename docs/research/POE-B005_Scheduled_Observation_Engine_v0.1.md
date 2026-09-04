# POE-B005 — Scheduled Observation Engine v0.1

Status: additive implementation evidence; not a frozen benchmark corpus.

## Product intent

The Scheduled Observation Engine records meaningful deterministic changes between immutable point-in-time Signals. It is research infrastructure for repeated observations, future alert delivery, and future agents; it does not schedule jobs, recalculate Signals, recommend trades, or implement brokerage, portfolio, or order behavior.

## Architecture decision

The scheduler-independent core is `SignalRepository → observe_signal_changes → ObservationEventRepository`. Integration occurs after successful Signal persistence at the shared technical-observation boundary already used by scheduled/default scans, Universe Analysis, Opportunity Discovery, and supported manual analysis. This avoids duplicating Signal calculations and gives all workflows identical event semantics. Source scan identity retained on each Signal distinguishes their provenance.

The existing Universe Analysis “What Changed” detector was reviewed and its deterministic UUID, atomic-event, provenance, and inspectability principles were reused. Its snapshot-level membership, availability, rank, and comparability rules are not reused because Observation Events compare same-security Signals rather than universe snapshots. Model Lab is the single research-facing event ledger, avoiding a competing Universe Analysis interaction path.

## Event contract and persistence

`observation-event.v0.1` records deterministic event ID, ticker, observation time, Signal family, model ID/version, event type, prior/current Signal IDs and as-of values, changed field and prior/current values, deterministic importance, components, metadata, source scan ID, creation time, and schema version. The dedicated additive `observation_events` table has immutable Signal foreign-key lineage and SQLite/Postgres indexes for security and model history. Repository initialization bootstraps legacy databases without modifying existing Signal or Outcome rows.

Event identity is UUIDv5 over schema version, prior Signal ID, current Signal ID, event type, and field. Identical retries return an idempotent non-insert; conflicting immutable content is rejected.

## Event semantics

Directional Technical Setup events include `directional.trend_state_changed` and `directional.direction_changed`. The engine uses only existing `source_trend_state` and Signal direction semantics; it does not invent bearish meaning or emit raw score-delta events. Adjacent trend/direction changes are notable; multi-state trend moves and direct bullish/bearish reversals are major.

Volatility Context events include `volatility.regime_changed` and `volatility.trend_changed`. Adjacent regime changes and all volatility-trend changes are notable; regime jumps of two or more ordered bands are major. Volatility metadata explicitly records that directional interpretation is false. No bullish/bearish meaning is applied.

## Comparison, idempotency, and point-in-time policy

Each newly inserted Signal is compared only with the most recent strictly earlier Signal matching ticker, family, model ID, and model version. No event is emitted for the first Signal, unchanged state, incompatible family/version, or a Signal at the same timestamp. A historical replay uses only Signals with `as_of < current.as_of`; later persisted Signals cannot become its prior observation. Distinct intraday timestamps may form history, while exact same-timestamp retries do not. Historical Signals are never mutated.

## Rejected alternatives

- Cron and scheduler redesign were rejected because job triggering is outside the analytical contract.
- Snapshot events were not overloaded because they encode universe membership and cross-sectional comparison rather than Signal lineage.
- Signals and Outcomes were not overloaded because point-in-time state, subsequent realized results, and state transitions are distinct evidence types.
- Score-by-score events, learned thresholds, LLM descriptions, alerts, and automatic thesis decisions were deferred to avoid noise and unsupported interpretation.
- Global uniqueness based only on ticker/time was rejected because event provenance must include the exact prior/current Signal pair.

## Automated evidence

`tests/test_scheduled_observation_engine.py` covers first observation, unchanged state, directional and volatility transitions, simultaneous events, family/version isolation, deterministic identity, retry behavior, chronological prior selection, future exclusion, same-timestamp policy, SQLite legacy bootstrap, Postgres schema structure, shared scheduled/manual persistence, and Model Lab rendering without directional volatility language. Existing Signal, Outcome, technical scan, Universe Analysis, Opportunity Discovery, and Model Lab suites provide regression evidence.

## Manual acceptance evidence

Pending product-owner acceptance. A deterministic two-observation developer path may seed or run two dated analyses with a supported state transition, then inspect Model Lab → Recent Observation Events for prior/current values and Signal provenance. Live data is not required to fabricate a transition.

## Deferred

No cron redesign, alert delivery, brokerage/trading, portfolio construction, GARCH-family model, implied-volatility comparison, options scoring change, ensemble, AI analyst, LLM summary, thesis decision, simulation, optimization, benchmark freeze, or v0.5 work is included.
