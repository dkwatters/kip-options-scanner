# POE-B002 — Signal Integration Correction

## Evidence chain

The original Signal & Outcome Foundation v0.1 implementation introduced the immutable Signal contract, the corrected `technical-setup-signal-v0.1.1` adapter, atomic persistence, and Model Lab. Component-level automated acceptance passed.

Manual acceptance then used the feature-worktree Streamlit application to create a Research Universe containing NVDA, validate NVDA through the production Tradier provider, run Analyze Universe, and review NVDA successfully. Model Lab nevertheless displayed: “No signals have been recorded yet. Future Technical Analysis Model scans will add versioned signals here.” This UI observation is the preserved equivalent of the empty-state screenshot finding.

The subsequent read-only diagnostic established that Universe Analysis archived `technical_characterization` but never entered the Signal adapter or `SignalRepository`; only Opportunity Discovery contained that integration. Both pages used the same configured Research Repository target, ruling out a worktree database-path mismatch.

## Corrective implementation

The correction associates derived Signal production with a shared technical-observation application boundary: archive successfully generated technical observations first, derive versioned Signals, then persist the Signal batch atomically. Universe Analysis and Opportunity Discovery both use this boundary and resolve their observation and Signal repositories from one target. A Signal failure retains the archived analysis but produces an explicit partial-success warning. A total failure to obtain TAM rows is no longer converted into an apparently successful empty Signal batch.

## Before and after

- Before: Analyze Universe could archive and display NVDA while Model Lab remained empty.
- After: the persisted NVDA technical observation produces its deterministic `technical-setup-signal-v0.1.1` Signal, and Model Lab reads it from the same repository.
- Before: Opportunity Discovery could retain a Signal error only in session state, without rendering it.
- After: both supported UI paths display “Analysis archived, but derived Signals were not persisted” with sanitized exception detail.

## Automated evidence

`tests/test_signal_integration.py` exercises the application integration rather than manually seeding `research_signals`: Universe Analysis through Model Lab, Opportunity Discovery, retry idempotency, conflict atomicity, visible partial success, and missing-TAM behavior. Existing Signal/Outcome, Universe Analysis, Opportunity Discovery, and Model Lab coverage remains part of regression acceptance.

POE-B001 is unchanged.
