# Developer Test Data Controls v0.1

## Purpose

Developer Test Data Controls provide repeatable, local QA states for the Research Universe and Universe Analysis experience. They shorten UI smoke-testing cycles without waiting for market movement and without invoking market-data providers, AI, scoring, or research generation.

## Developer-only gate

The controls render only when `ENABLE_DEVELOPER_TOOLS` is explicitly set to a true value (`true`, `1`, `yes`, or `on`). The default is disabled. This is a visibility and execution gate; normal application behavior does not call the demo service.

Enable locally in PowerShell before starting Streamlit:

```powershell
$env:ENABLE_DEVELOPER_TOOLS="true"
streamlit run app.py
```

Disable the controls by removing the variable or setting it to `false`:

```powershell
Remove-Item Env:ENABLE_DEVELOPER_TOOLS
```

## Isolation strategy

Every demo universe ID begins with `demo-`. Snapshot and run IDs also contain explicit `demo-` ownership, titles begin with `Demo`, provenance is marked `demo-fixture`, and snapshot provider metadata is `deterministic-demo`.

Scenario generation is deterministic and idempotent. Saving the same scenario again reuses the same immutable snapshot identities and content. Demo technical rows are held only in the active Streamlit session; they are not inserted into production technical-observation tables.

Reset uses the snapshot repository's narrowly constrained `delete_demo_snapshots()` operation. It accepts only the exact `demo-` prefix and deletes rows by demo universe identity. It never truncates tables, never selects records by ticker, and never deletes non-demo snapshots. The UI requires an explicit confirmation checkbox.

## Scenarios

- **First run:** one completed snapshot and no baseline.
- **Comparable change:** two fully compatible snapshots with deterministic technical transitions, attention candidates, and change events.
- **No change:** two fully compatible snapshots whose meaningful deterministic states do not change.
- **Membership change:** one member is removed and one is added; emitted changes remain membership events rather than performance events.
- **Limited comparability:** universe version and availability differ; the comparison remains limited, rank claims are suppressed, and caveats remain available.

Each multi-snapshot scenario traverses the production deterministic pipeline:

```text
Snapshot
  -> Comparison
  -> Change Detection
  -> Interpretation Input
  -> Selection
  -> Presentation
```

The fixtures do not handcraft presentation objects.

## QA workflow

1. Set `ENABLE_DEVELOPER_TOOLS=true` locally.
2. Launch Streamlit with `streamlit run app.py`.
3. Open **Universe Analysis** and expand **Developer tools**.
4. Generate **First-run scenario** and inspect the no-baseline state.
5. Generate **Comparable change scenario** and inspect **What changed** and attention sections.
6. Generate **No-change scenario** and inspect the empty change state.
7. Generate **Membership change scenario** and inspect membership additions/removals.
8. Generate **Limited-comparability scenario** and verify visible caveats and suppressed claims.
9. Select the reset confirmation and choose **Reset demo data**.

The panel reports the demo universe name/ID and number of newly created snapshots. Scenario generation also activates the current demo run for Universe Analysis.

## Deterministic guarantees

- Fixed universe, run, snapshot, member, observation, and evidence identities.
- Fixed timestamps and technical fixture values.
- Immutable snapshot persistence through the existing repository.
- Stable scenario and presentation results for identical inputs.
- No uncontrolled duplicates on repeated generation.

## Explicit exclusions

This feature does not change RCE prompts or reasoning, candidate generation, SAM, Opportunity modules, Study Protocols, scoring, technical indicator logic, scheduled scans, cloud jobs, retention behavior, provider integrations, Morning Coffee, or AI behavior. It is not a database reset utility and cannot delete arbitrary application data.

## Future beta QA

These scenarios can support a bounded beta acceptance checklist and screenshot regression workflow later. They should remain fixtures over the deterministic contracts; future scenarios should not introduce parallel analytical or UI-only truth.
