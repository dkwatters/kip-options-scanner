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

Each submitted Signal, including an identical persistence retry, is compared only with the most recent strictly earlier Signal matching ticker, family, model ID, and model version. ISO timestamps and the repository's legacy 12-hour Eastern display timestamps are normalized to UTC instants before ordering. No event is emitted for the first Signal, unchanged state, incompatible family/version, or a Signal at the same instant. A historical replay uses only Signals earlier than the current instant; later persisted Signals cannot become its prior observation. Distinct intraday timestamps may form history, while exact same-time retries do not. Historical Signals are never mutated.

## Rejected alternatives

- Cron and scheduler redesign were rejected because job triggering is outside the analytical contract.
- Snapshot events were not overloaded because they encode universe membership and cross-sectional comparison rather than Signal lineage.
- Signals and Outcomes were not overloaded because point-in-time state, subsequent realized results, and state transitions are distinct evidence types.
- Score-by-score events, learned thresholds, LLM descriptions, alerts, and automatic thesis decisions were deferred to avoid noise and unsupported interpretation.
- Global uniqueness based only on ticker/time was rejected because event provenance must include the exact prior/current Signal pair.

## Automated evidence

`tests/test_scheduled_observation_engine.py` covers first observation, unchanged state, directional and volatility transitions, simultaneous events, family/version isolation, deterministic identity, retry behavior, chronological prior selection, future exclusion, same-timestamp policy, SQLite legacy bootstrap, Postgres schema structure, shared scheduled/manual persistence, and Model Lab rendering without directional volatility language. Existing Signal, Outcome, technical scan, Universe Analysis, Opportunity Discovery, and Model Lab suites provide regression evidence.

## Manual acceptance evidence

Product-owner manual acceptance is complete and PASS on a fresh isolated SQLite database. Step 1 reported `signal_inserted_count=2 signal_retry_count=0 event_inserted_count=0 event_retry_count=0`: HOOD bullish, conviction 0.5, constructive; NVDA normal/stable, direction N/A, conviction 0; neither family had events. Step 2 reported `signal_inserted_count=2 signal_retry_count=0 event_inserted_count=4 event_retry_count=0`: HOOD bullish -> neutral and constructive -> mixed; NVDA normal -> elevated and stable -> expanding. Model/version, source scan, prior Signal ID, and provenance were visible in Model Lab. Volatility remained explicitly non-directional.

Step 2 retry reported `signal_inserted_count=0 signal_retry_count=2 event_inserted_count=0 event_retry_count=4`, proving no duplicate Signals or Events for this fixed history. The fixture constructs Signals directly without analytical model calls and honors `--database` for both repositories. It appends rather than resets: running Step 1 after Step 2 retains all history. See [manual acceptance procedure](Observation_Event_Manual_Acceptance_v0.4.md).

## Pre-PR independent review (2026-09-09)

Status: BLOCKED pending a product-owner decision about late-arriving historical Signals. Manual acceptance above remains PASS for its tested scenario.

Reproduction on isolated SQLite: persist A at August 1 (bullish/constructive) and C at August 3 (neutral/mixed), then observe C. Two A -> C events are inserted. Persist B at August 2 (bullish/constructive), then submit the identical C again. Two additional B -> C events are inserted, with zero event retries; all four remain. Event IDs are stable for an exact prior/current pair, but the selected prior can change after a backfill. The current implementation therefore does not guarantee retry idempotency across changes to earlier history. No policy correction was made: freezing the original comparison, rejecting recomparison, or explicitly recording revised comparisons requires a product decision. Zero-event comparisons also need to be considered in that decision, since no comparison receipt is currently stored.

Corrective review changes normalize event-ledger timestamps before sorting/limiting, detach and recursively freeze nested event evidence, expose Opportunity Discovery Event persistence errors, and expand relevant CI path filters. Technical Setup and Volatility Context calculations are unchanged.

Signal and Event writes use separate transactions. Signal commit can succeed while Event commit fails; the shared boundary exposes separate errors and counts. Replaying the exact archived input recovers Event persistence when compatible history has not changed. Starting a new scan is not equivalent to replaying the original input. Concurrent writers can encounter visible uniqueness/locking errors and require retry; no duplicate primary key is accepted. PostgreSQL DDL was structurally reviewed, but no live PostgreSQL integration run was performed. The engine and recent-event listing load matching history into memory for normalized ordering.

Final local validation used `C:\Users\dkwat\kip-options-scanner\.venv\Scripts\python.exe`: the focused engine/Signal/integration/family/volatility/Model Lab/technical scan selection passed 55 tests; `python -m pytest -q -m "not authoritative_rce_evidence"` passed 521 tests and 21 subtests, with 3 deselected. Both runs emitted one pytest cache-permission warning. The known Launchpad identity/environment failure did not reproduce, so no pre-existing-failure classification or baseline comparison was needed. `python -m compileall -q app.py src tests` and `git diff --check` passed. These passing suites do not cover or resolve the demonstrated backfill policy blocker.

The standard PR suite still excludes only marked `authoritative_rce_evidence` tests. Dedicated authoritative validation remains separate, checksum-verified, and fail-closed. POE-B001/B002/B003/B004 and frozen evidence are unchanged; no new benchmark corpus was created.

## Deferred

No cron redesign, alert delivery, brokerage/trading, portfolio construction, GARCH-family model, implied-volatility comparison, options scoring change, ensemble, AI analyst, LLM summary, thesis decision, simulation, optimization, benchmark freeze, or v0.5 work is included.
