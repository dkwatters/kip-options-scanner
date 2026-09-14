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

Each never-evaluated Signal selects the most recent strictly earlier Signal matching ticker, family, model ID, and model version. Its durable first-observation comparison is authoritative. Completed retries return the original result without selecting history again; incomplete retries resume the reserved prior identity. ISO timestamps and the repository's legacy 12-hour Eastern display timestamps are normalized to UTC instants before ordering. No event is emitted for the first Signal, unchanged state, incompatible family/version, or a Signal at the same instant. A historical replay uses only Signals earlier than the current instant; later persisted Signals cannot become its prior observation. Distinct intraday timestamps may form history, while exact same-time retries do not. Historical Signals are never mutated.

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

Historical review status: BLOCKED at commit 9590156, subsequently resolved by the product-policy correction below. Manual acceptance above remains PASS for its tested scenario.

Reproduction on isolated SQLite: persist A at August 1 (bullish/constructive) and C at August 3 (neutral/mixed), then observe C. Two A -> C events are inserted. Persist B at August 2 (bullish/constructive), then submit the identical C again. Two additional B -> C events are inserted, with zero event retries; all four remain. Event IDs are stable for an exact prior/current pair, but the selected prior can change after a backfill. That implementation did not guarantee retry idempotency across changes to earlier history. The review stopped for a product decision because no durable receipt existed for zero-event comparisons. The selected correction is recorded below.

Corrective review changes normalize event-ledger timestamps before sorting/limiting, detach and recursively freeze nested event evidence, expose Opportunity Discovery Event persistence errors, and expand relevant CI path filters. Technical Setup and Volatility Context calculations are unchanged.

Signal and Event writes use separate transactions. Signal commit can succeed while Event commit fails; the shared boundary exposes separate errors and counts. In the original implementation, replay recovery required compatible history to remain unchanged. The reservation/completion mechanism below removes that dependency after a selection is reserved. Starting a new scan is not equivalent to replaying the original input. Concurrent writers can encounter visible uniqueness/locking errors and require retry; no duplicate primary key is accepted. PostgreSQL DDL was structurally reviewed, but no live PostgreSQL integration run was performed. The engine and recent-event listing load matching history into memory for normalized ordering.

Pre-policy-correction local validation used `C:\Users\dkwat\kip-options-scanner\.venv\Scripts\python.exe`: the focused engine/Signal/integration/family/volatility/Model Lab/technical scan selection passed 55 tests; `python -m pytest -q -m "not authoritative_rce_evidence"` passed 521 tests and 21 subtests, with 3 deselected. Both runs emitted one pytest cache-permission warning. The known Launchpad identity/environment failure did not reproduce, so no pre-existing-failure classification or baseline comparison was needed. `python -m compileall -q app.py src tests` and `git diff --check` passed. These passing suites do not cover or resolve the demonstrated backfill policy blocker.

The standard PR suite still excludes only marked `authoritative_rce_evidence` tests. Dedicated authoritative validation remains separate, checksum-verified, and fail-closed. POE-B001/B002/B003/B004 and frozen evidence are unchanged; no new benchmark corpus was created.

## Product-policy correction: immutable first observation

The product owner selected immutable first-observation semantics: events answer what changed when the Signal was first observed using compatible history then known. They do not reconstruct what would have happened if all subsequently backfilled history had always existed. The first completed result remains authoritative, including no-prior and unchanged-state results.

`observation_comparisons` stores an immutable UUIDv5 comparison identity, current/prior Signal foreign keys (prior nullable), ticker, family, model ID/version, original as-of timestamps, evaluation/creation time, event count, source scan ID, metadata with both evidence references and prior source scan, reserved event IDs, schema `observation-comparison.v0.1`, and policy `first-observation.v0.1`. Identity includes schema, policy, and current Signal ID; a unique constraint on current Signal ID plus policy prevents a second production comparison. Nested metadata is immutable. Identical repository writes are retries; conflicting immutable content raises visibly. Evaluation/creation timestamps record the actual initial reservation time, preserved on retry.

A separate append-only `observation_comparison_completions` receipt distinguishes a reserved/incomplete selection from a completed comparison. No comparison means never evaluated; a receipt with count zero means evaluated without events; a receipt with positive count means evaluated with events. No synthetic Observation Event represents a zero-event result. Existing Signal-only SQLite databases bootstrap additively, and the same portable additive DDL is used for PostgreSQL with Signal and comparison foreign keys and a model-history index.

Transactions: Signal persistence remains independent. The selected comparison is first reserved durably so an interrupted Event write cannot choose a different prior later. All events for that comparison and its completion receipt then commit atomically. Failure rolls back events and completion together while retaining the immutable selection; replay resumes that exact selection. Before any reservation commits, no durable evaluation exists and retry uses then-available history. Atomicity is per comparison rather than across a multi-Signal batch; completed items in a partially failed batch remain durable and retry safely. Error results retain counts for already-committed items; a regression verifies partial-batch counts and recovery. SQLite serializes completion with `BEGIN IMMEDIATE`; PostgreSQL locks the comparison row with `FOR UPDATE`. Concurrent reservation attempts use the unique policy/current key and resume the winning record.

Completed retries load the receipt and recorded counts without querying candidate Signals or emitting events. Event retry counts remain compatible with the original acceptance fixture; separate comparison completion/retry counts make zero-event retries observable in engine and scheduled-scan results. An interrupted completion counts as a newly completed comparison when recovered. Backfilled B may become the prior for a newly evaluated Signal D whose instant is later than B and for which B is the latest compatible earlier Signal; it cannot change already-completed C. Tests also place D before C to prove future exclusion.

Older development databases with events but no comparison receipt fail visibly on affected Signals; the engine does not guess which historical comparison was first or invent missing zero-event history. There is no automatic destructive reset or evidence migration. Use a fresh isolated database for the developer acceptance fixture. Legacy databases containing Signals only can establish new first-observation comparisons normally.

`tests/test_observation_comparisons.py` provides executable backfill regression evidence for eventful, unchanged, and no-prior results; candidate-history lookup is explicitly forbidden during completed retries. It also covers pending recovery after event inserts fail, backfills during that failure, deterministic/versioned identity, duplicate persistence, immutable-content conflicts, SQLite bootstrap/foreign keys, PostgreSQL DDL structure, concurrent observers, and fail-closed handling of unreceipted development events. Run `python -m pytest -q tests/test_observation_comparisons.py` for the developer backfill path; no additional product-owner UI acceptance is required by this correction.

Future explicit historical recomparison/rebuild is deferred. It must use a new policy/version or explicit rebuild lineage, preserve original evidence, and visibly distinguish recomputed history. No recomparison UI, rebuild command, or new analytical calculation is implemented here.


## Policy-correction validation

Historical policy-correction status: READY FOR PRE-PR REVIEW at e94c077; push/PR was deferred until the final review below.

- Focused regression command: `python -m pytest -q tests/test_observation_comparisons.py tests/test_scheduled_observation_engine.py tests/test_signal_foundation.py tests/test_signal_integration.py tests/test_typed_signal_families.py tests/test_volatility_context.py tests/test_model_lab_streamlit.py tests/test_technical_scan.py` - **68 passed**, one pytest cache-permission warning, 16.27 seconds. Includes all 13 explicit comparison/backfill/recovery regressions.
- Full CI-equivalent command: `python -m pytest -q -m "not authoritative_rce_evidence"` - **534 passed, 3 deselected, 21 subtests passed**, one pytest cache-permission warning, 49.98 seconds. No test failure or Launchpad failure reproduced.
- `python -m compileall -q app.py src tests scripts` and `git diff --check` passed.
- Fresh SQLite CLI fixture, executed with explicit `--database` and steps 1, 2, 2: counts remained `(2 inserted Signals, 0 retries, 0 events, 0 event retries)`, `(2, 0, 4, 0)`, then `(0, 2, 0, 4)`. Four immutable comparisons and four completion receipts remained. The fixture performs no analytical model calls and was not changed.
- CI path filters include the comparison module and regression file. Standard/dedicated authoritative-evidence separation remains unchanged. POE-B001 through POE-B004 and frozen evidence are untouched.

PostgreSQL validation remains structural rather than live. Initial candidate selection and reservation are not one database snapshot: concurrent history insertions after candidate loading do not change the selected evidence. Once reserved, recovery preserves that selection permanently. Existing matching-history queries remain in-memory and may need indexing/normalized timestamp improvements at larger scale. These limitations do not permit completed comparisons to be silently recomputed.


## Final pre-PR acceptance review

Status: PASS after one final repository correction; approved scope is push and PR preparation, without merge.

The review reproduced a standalone Event writer bypass: after A -> C was completed, `save_events` could append B -> C events for the same current Signal. The new regression failed before correction (`DID NOT RAISE ObservationComparisonConflict`). The standalone API now permits only identical already-persisted retries for reserved production comparisons; new comparison events must go through atomic completion. This also protects authoritative zero-event/no-prior comparisons and prevents pending events from being published without their completion receipt. The repository rechecks unreceipted legacy events during reservation, closing the gap after the engine's initial legacy check. SQLite uses `BEGIN IMMEDIATE`; PostgreSQL serializes these write paths on the current Signal with `FOR NO KEY UPDATE`, then locks the comparison for completion. Signal content is never changed by these locks. Five added cases cover the bypass and legacy-write timing.

All 16 requested invariants were reviewed across Signal persistence, immutable reservations, Events, completion receipts, and retry recovery. The current/policy unique constraint enforces one authority; normalized strict-earlier selection excludes future and same-time candidates; completed retries do not query candidate history; pending recovery uses its reserved prior; events and completion commit together; immutable conflicts fail visibly. Backfills cannot change completed or reserved results. Directional/volatility calculations, Signal/Outcome behavior, and non-directional volatility remain unchanged. Supported TAM/research scans, Universe Analysis, Opportunity Discovery, and manual analysis continue through the shared boundary; partial-batch counts/errors remain visible. Model Lab retains family/model/version filtering, exact immutable lineage/provenance, normalized recent-event ordering, and research-only language.

Final local validation:

- `python -m pytest -q tests/test_observation_comparisons.py tests/test_scheduled_observation_engine.py`: **35 passed**, one cache-permission warning, 4.26 seconds.
- Relevant persistence/integration/UI selection (`test_signal_foundation`, `test_signal_integration`, `test_typed_signal_families`, `test_volatility_context`, `test_model_lab_streamlit`, `test_technical_scan`, `test_research_repository`, `test_research_universe_analysis`, `test_universe_analysis_streamlit`): **68 passed**, one cache-permission warning, 7.61 seconds.
- `python -m pytest -q -m "not authoritative_rce_evidence"`: **539 passed, 3 deselected, 21 subtests passed**, one cache-permission warning, 21.25 seconds. No Launchpad failure reproduced.
- `python -m compileall -q app.py src tests scripts`, working-tree whitespace check, and full accepted-base diff whitespace check passed.
- Fresh CLI acceptance with explicit `--database` and steps 1/2/2 remained `(2,0,0,0)`, `(2,0,4,0)`, `(0,2,0,4)` for Signal inserts/retries and Event inserts/retries. Final counts: four Signals, four Events, four comparisons, four completion receipts. Product-owner manual acceptance remains PASS.

SQLite bootstrap is additive with foreign keys enabled. PostgreSQL DDL remains additive/idempotent and was structurally reviewed; no live PostgreSQL validation is claimed. Legacy Signal/Outcome data remains readable; development-era unreceipted events are preserved and fail visibly on attempted normal-path reinterpretation. No destructive migration or corpus freeze occurred. POE-B001/B002/B003/B004, analytical calculations, frozen evidence, and the separate fail-closed authoritative CI workflow are unchanged. PR path filters cover the relevant v0.4 code and tests. The documented scale, separate Signal-transaction, and explicit future recomparison limitations remain.

## Deferred

No cron redesign, alert delivery, brokerage/trading, portfolio construction, GARCH-family model, implied-volatility comparison, options scoring change, ensemble, AI analyst, LLM summary, thesis decision, simulation, optimization, benchmark freeze, or v0.5 work is included.
