# RCE Benchmark Baseline v0.1

Status: live baseline not executed.

The repeatable benchmark harness is implemented, but the 17-domain live OpenAI run was intentionally not started because this sprint requires explicit approval of API cost and no such approval was provided. This file is the baseline report destination; it must not be interpreted as benchmark results.

The complete 17-domain baseline must not be run until the benchmark-runner checkpoint is committed and pushed; one narrowly selected live OpenAI benchmark has succeeded; and live token, latency, estimated-cost, persistence, exports, and scoring have been validated.

## Execution metadata

- Execution date: not executed
- Provider: OpenAI intended; not invoked
- Model: `gpt-4.1-mini` default intended; not invoked
- Prompt version: `rce-multi-stage-artifact-pipeline-v0.1`
- Benchmark corpus version: v0.2 (17 reviewed fixtures)
- Benchmarks executed: 0
- Successful runs: 0
- Failed runs: 0

## Benchmark scores

No live scores are available.

## Aggregate score by metric

No live aggregate metrics are available.

## Missing must-include companies

Not evaluated.

## Must-exclude violations

Not evaluated.

## Category gaps

Not evaluated.

## Listing violations and invalid candidates

Not evaluated.

## Parser and provider issues

No live provider or parser calls were made.

## Recurring failure patterns

Not evaluated. The harness will report patterns without treating overall-score movement alone as improvement or regression.

## Latency distribution, token usage, and estimated API cost

- Latency: not available
- Input tokens: 0
- Cached input tokens: 0
- Output tokens: 0
- Reasoning tokens: 0
- Estimated API cost incurred: $0.00

## Benchmarks requiring manual review

Not evaluated. Unexpected candidates from a live run will be retained as `needs_verification` until classified by a reviewer.

## Known limitations

- The benchmark corpus is reviewed reference data, not absolute truth.
- The current RCE candidate artifact schema does not provide structured evidence fields; evidence completeness is reported as an explicit limitation and does not fail a run.
- Human-review scores remain separate from the deterministic overall score in v0.1.
- Listing and public-status checks are limited to facts deterministically observable from the current artifact and reviewed fixture.
- No benchmark fixture is automatically changed from RCE output or reviewer activity.

## Authorized live baseline command

After explicit API-cost approval and configuration of `OPENAI_API_KEY`:

```powershell
python scripts/run_rce_benchmarks.py --all --provider openai --persist --label baseline-v0.1 --export-json data/research/rce_benchmark_baseline_v0.1.json --export-markdown docs/research/RCE_Benchmark_Baseline_v0.1.md
```
