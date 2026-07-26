# RCE Enrichment Benchmark Observability v0.1

This benchmark is instrumentation for human review. It does not change enrichment
prompts, candidate-generation behavior, Discovery Lens semantics, production RCE
behavior, or legacy benchmark scoring.

## Matched sensitivity fixture

`tests/fixtures/rce_enrichment_sensitivity_scenarios_v01.json` holds four cases
with the identical base question:

1. Question only.
2. The same question plus the `NVDA` manual anchor.
3. The same question plus the existing `ai-networking` topic (`NVDA`, `ANET`).
4. The same question plus that manual anchor and topic.

This fixture family isolates context changes. The original enrichment fixture is
retained, and its report explicitly notes that its different questions confound
context-sensitivity comparisons.

## Output bound

Live enrichment benchmark provider instances set `max_output_tokens=8000`.
The bound is conservative for the structured review response and the enrichment
prompt's expected 25-50 candidates. The provider default remains unbounded, so
production and other benchmark callers do not receive this parameter.

## Evidence limitation

The enrichment provider call does not use live web/search retrieval. Evidence
references are model-produced; evidence completeness does not equal evidence
correctness; and source truthfulness is not validated. This benchmark evaluates
context-aware candidate discovery behavior, not retrieval-grounded evidence
quality.

## PowerShell setup

From the repository root, load only `OPENAI_API_KEY` from the existing `.env`
into the current PowerShell session without displaying its value:

```powershell
$openAIEnvLine = Get-Content -LiteralPath .env | Where-Object { $_ -match '^\s*OPENAI_API_KEY\s*=' } | Select-Object -First 1
if (-not $openAIEnvLine) { throw 'OPENAI_API_KEY is missing from .env' }
$env:OPENAI_API_KEY = ($openAIEnvLine -split '=', 2)[1].Trim().Trim('"').Trim("'")
if ([string]::IsNullOrWhiteSpace($env:OPENAI_API_KEY)) { throw 'OPENAI_API_KEY is empty in .env' }
```

The recommended explicitly authorized live command is:

```powershell
python scripts/run_rce_enrichment_benchmarks.py --provider openai --fixture tests/fixtures/rce_enrichment_sensitivity_scenarios_v01.json --export-json data/research/rce_enrichment_sensitivity_live_v01.json --export-markdown data/research/rce_enrichment_sensitivity_live_v01.md
```

That command makes exactly four logical provider requests. SDK transport retries
may occur under the SDK's defaults; the benchmark adds no application retry loop.
Artifacts are written only when their corresponding export arguments are supplied,
and no database rows are written.
