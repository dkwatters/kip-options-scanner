# Robinhood / HOOD omission audit — Sprint 2

This is a read-only trace of certified run `baseline-v0.1-providerfix`, run ID
`35a03051edb64ffb8d1b275664e6e58c`. No benchmark or provider call was made.

1. The question was: “Which public companies and reference entities matter across
   payments, digital banking, BNPL, and wealth-platform fintech?”
2. The raw provider response is unavailable locally. The certified export references
   `data\research\rce_benchmark_runs\baseline-v0.1-providerfix\35a03051edb64ffb8d1b275664e6e58c\raw_response.json`,
   but that file is absent.
3. The parsed RCE artifact is also unavailable at its referenced `parsed_artifact.json`.
   The export records 17 raw and 17 parsed candidates.
4. The evaluator matches exact normalized ticker before name. The exported HOOD record
   is `returned=false`, `returned_rank=null`, and `validation_status=not_returned`.
   Thus HOOD was not a structured candidate supplied to evaluation and was not rejected
   by entity validation.
5. The certified baseline retains HOOD as an expected Fintech security marked
   `expected_missing`. There is no candidate-limit or cutoff operation in the evaluator.
6. The Explorer reads every exported candidate with `returned=true`; it does not filter
   HOOD. The export supplies HOOD only as a missing expected candidate.

Conclusion: the last conclusive layer is that HOOD was absent from the parsed structured
candidate list received by evaluation. It was not removed by validation, scoring, cutoff
logic, baseline export, or Explorer projection. The missing raw and parsed artifacts are
required to distinguish provider omission, narrative-only mention, or parser loss; no
stronger conclusion is supported locally.

This is a broader coverage gap rather than an isolated Robinhood name mismatch. The
authored-vs-RCE comparison also marks FIS, Fiserv, Global Payments, Marqeta, Chime,
Klarna, Nu Holdings, Interactive Brokers, and authored Block as authored-only. Block,
Inc. appears separately with returned ticker SQ while the authored corpus records XYZ;
ticker-first matching correctly does not merge those conflicting identifiers. The
same-ticker naming variant (`Block` / `Block, Inc.` with SQ) is covered by a deterministic
agreement test without changing the certified fixture, baseline, or authored artifact.
