# v0.4 Observation Event manual acceptance

Use the scheduled-observation-engine-v0.1 worktree. The sibling
volatility-context-v0.1 worktree does not contain this seed script or engine.
Stop any previous acceptance Streamlit process with Ctrl+C. During this
demonstration, open Model Lab without running Analyze Universe or other scans.

## Fresh Step 1

Every rerun uses a new GUID-named temp directory. This guarantees a clean
database without deleting earlier evidence. Step 1 is an idempotent append,
not a reset: running it after Step 2 retains all four Signals and four events.

```powershell
Set-Location 'C:\Users\dkwat\kip-options-scanner\.worktrees\scheduled-observation-engine-v0.1'
$python = 'C:\Users\dkwat\kip-options-scanner\.venv\Scripts\python.exe'
if (!(Test-Path -LiteralPath '.\scripts\seed_observation_event_acceptance.py')) { throw 'Wrong worktree' }
$runDir = Join-Path ([IO.Path]::GetTempPath()) ('kip-v04-acceptance-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $runDir -ErrorAction Stop | Out-Null
$db = Join-Path $runDir 'acceptance.sqlite'
if (Test-Path -LiteralPath $db) { throw 'Fresh database required' }
$env:RESEARCH_REPOSITORY_BACKEND = 'sqlite'
$env:RESEARCH_SQLITE_PATH = $db
& $python -m scripts.seed_observation_event_acceptance --database $db --step 1
if ($LASTEXITCODE -ne 0) { throw 'Step 1 failed; do not launch Model Lab' }
& $python -c "from src.research_repository import research_repository_target_from_env; print(research_repository_target_from_env())"
$db
```

Expected CLI: `signal_inserted_count=2 signal_retry_count=0 event_inserted_count=0 event_retry_count=0`.
The printed target must be SQLite at the printed absolute `$db`.
Inspect the actual persisted contents:

```powershell
$inspect = @'
import json, sqlite3, sys
from pathlib import Path
with sqlite3.connect(Path(sys.argv[1]).resolve().as_uri() + '?mode=ro', uri=True) as c:
    c.row_factory = sqlite3.Row
    tables = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    signals = [dict(r) for r in c.execute('SELECT signal_id,ticker,as_of,model_id,model_version,direction,conviction,components,metadata FROM research_signals ORDER BY as_of,ticker')]
    events = [dict(r) for r in c.execute('SELECT event_id,ticker,event_type,field,prior_value,current_value,prior_signal_id,current_signal_id FROM observation_events ORDER BY ticker,field')] if 'observation_events' in tables else []
    print(json.dumps({'signals':signals,'events':events,'signal_count':len(signals),'event_count':len(events)}, indent=2))
'@
$inspect | & $python - $db
& $python -m streamlit run .\app.py --server.port 8514
```

Open http://localhost:8514 and select Model Lab. Use this exact port, not an
old browser tab. If occupied, stop the old process or choose an unused port
and open that same port.

| Stage | Directional | Volatility | Total events |
|---|---|---|---|
| Step 1 | 1 HOOD: bullish, conviction 0.5, constructive | 1 NVDA: normal/stable, N/A, conviction 0 | 0 |
| Step 2 | 2 HOOD: original plus neutral, conviction 0, mixed | 2 NVDA: original plus elevated/expanding, N/A, conviction 0 | 4 |
| Retry Step 2 | Same 2 HOOD Signals | Same 2 NVDA Signals | 4 |

Directional model/version: `technical-setup-score` / `technical-setup-signal-v0.1.1`.
Volatility model/version: `volatility-context` / `volatility-context-v0.1`.
IDs: `acceptance-directional-1`, `acceptance-volatility-1`, then
`acceptance-directional-2`, `acceptance-volatility-2`.
Step 1 as-of/created-at: `2026-08-01T16:00:00-04:00`.
Step 2 as-of/created-at: `2026-08-02T16:00:00-04:00`.
These synthetic timestamps do not represent market-session calculations.

Components are empty: score, percentile, RV10, RV20, ATR, bandwidth and
data_quality are not seeded; corresponding UI fields are blank. Directional
trend state is persisted as `source_trend_state` metadata, not displayed as a
Signal ledger column. Step 2 displays its transition in Recent Observation
Events. No forward Outcomes are seeded. Both families initially show the
no-meaningful-changes message. The events table may be absent until initialized;
that also represents zero events.

## Step 2

After inspecting Step 1, press Ctrl+C in the same PowerShell window. Keep
`$db`, `$python`, and `$inspect` from above:

```powershell
& $python -m scripts.seed_observation_event_acceptance --database $db --step 2
if ($LASTEXITCODE -ne 0) { throw 'Step 2 failed' }
$inspect | & $python - $db
& $python -m streamlit run .\app.py --server.port 8514
```

Expected CLI: `signal_inserted_count=2 signal_retry_count=0 event_inserted_count=4 event_retry_count=0`.
Model Lab shows both historical Signals per family and two events per selected
family (four total), all with importance `notable`:

- HOOD `directional.direction_changed`: bullish -> neutral.
- HOOD `directional.trend_state_changed`: constructive -> mixed.
- NVDA `volatility.regime_changed`: normal -> elevated.
- NVDA `volatility.trend_changed`: stable -> expanding.

Each event links its family's `acceptance-*-1` prior Signal to its
`acceptance-*-2` current Signal, with source scan `acceptance-step-2`.

## Retry Step 2

Stop Streamlit with Ctrl+C again:

```powershell
& $python -m scripts.seed_observation_event_acceptance --database $db --step 2
if ($LASTEXITCODE -ne 0) { throw 'Retry failed' }
$inspect | & $python - $db
& $python -m streamlit run .\app.py --server.port 8514
```

Expected CLI: `signal_inserted_count=0 signal_retry_count=2 event_inserted_count=0 event_retry_count=4`.
Persisted counts remain four Signals and four events. UI counts remain two
Signals and two events per selected family.

## Database routing and discrepancy evidence

The seed CLI always uses SQLite at `--database`; it does not configure the UI.
Model Lab resolves `RESEARCH_REPOSITORY_BACKEND` and `RESEARCH_SQLITE_PATH`
from its own process environment, then uses the same target for events.
Set both before launching a new Streamlit process. An existing process does
not inherit later shell changes. Explicit environment values take precedence
over `.env` defaults. Without explicit settings, DATABASE_URL can select
Postgres; otherwise SQLite defaults to `data/research/opportunity_scans.sqlite`
relative to the working directory.

Read-only inspection of `%TEMP%\kip-v04-observation-acceptance.sqlite` during
the September 5 discrepancy investigation found two NVDA Signals, both from
`research-universe-20260905-210928-e95aab6e`, timestamp
`2026-09-05 09:09:28 PM EDT`. Neither acceptance ID was present.

- Directional `7f5c4e4d-fef9-5629-8150-2cd82d8e5408`: bullish, conviction 1,
  source_trend_state bullish_alignment, source_score 100.
- Volatility `c9ae353e-b544-58cc-b51c-586052fcd55d`: elevated/expanding,
  percentile 86.06965174129353, RV10 0.5831749795842249,
  RV20 0.4480247258421051, direction not_applicable, conviction 0,
  data_quality sufficient_history.
- No observation_events table (zero events); signal_outcomes empty.

This matches the reported UI exactly. The unchanged seed constructs Signals
directly; it never calls providers, price history, TAM or volatility
calculations. This database therefore does not contain a successful Step 1
from that script. Evidence cannot distinguish a failed command, a different
command target, or a subsequent database replacement. Running Python command
lines only showed relative `streamlit run app.py`; the live process's worktree
and environment were not established.

Classification: A (incomplete setup instructions) and C (non-fixture database
state observed, not a demonstrated repository isolation bug). The documented
transitions are correct. B/E were not reproduced; D is not demonstrated.
Fixed IDs accept identical retries and reject changed immutable content; they
cannot silently substitute NVDA for HOOD. Timestamps choose strictly earlier
compatible Signals and cannot explain the reported values. Reusing a stale
database retains prior rows, which is why every fresh run needs a new DB.

Unchanged fixture validation: 2 Signals/0 events after Step 1; 4 Signals/4
events after Step 2; 4 Signals/4 events after retry. Focused v0.4 tests: 13
passed. Relevant Signal, Volatility, Model Lab, technical scan, Universe
Analysis and integration regression tests: 57 passed. Browser acceptance
remains for the product owner; no product or fixture code was changed.

## Completed product-owner acceptance

Product-owner acceptance is now PASS on a fresh isolated SQLite database: Step 1 inserted two Signals and zero events; Step 2 inserted two Signals and four events; Step 2 retry inserted nothing and reported two Signal retries and four Event retries. The expected HOOD and NVDA transitions, model/version, source scan, prior Signal ID, and provenance were visible. Volatility remained non-directional. This supersedes the earlier pending-browser status above. See POE-B005 for the independent pre-PR backfill-idempotency blocker, which is outside this fixed-history scenario.
