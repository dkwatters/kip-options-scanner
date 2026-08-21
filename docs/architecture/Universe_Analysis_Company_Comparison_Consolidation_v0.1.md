# Universe Analysis Company Comparison Consolidation v0.1

## Product decision

Company comparison is the primary analytical workspace for Universe Analysis. A compact
Current Read remains above it, with comparison status, deterministic counts, important
caveats, and snapshot context. Long, repeated Leaders, Laggards, What Deserves Attention,
What Changed, and Membership Changes sections are no longer rendered above the table.

The comparison table and the company detail immediately below it provide the detail layer.
Selecting one current-company row is the only company-detail interaction.

## Deterministic authority boundary

The existing pipeline remains authoritative:

`Snapshot → Comparison → Change Detection → Interpretation Input → Selection → Presentation Contract → Streamlit adapter`

The adapter only projects presentation-contract facts onto comparison rows. It does not
calculate facts, rerank members, reinterpret event direction, alter selection capacity, or
change snapshot/comparison semantics. Current technical fields and rank continue to come
from the existing ranked Company Comparison model. No provider or AI call is introduced.

## Row annotation mapping

Presentation facts are joined to current rows with stable matching identity, preferring a
normalized ticker when available and retaining matching keys and source identities for
traceability.

| Presentation source | Comparison projection |
| --- | --- |
| Leaders | `Intelligence: Leader` |
| Laggards | `Intelligence: Laggard` |
| What Deserves Attention | `Intelligence: Attention` and attention priority |
| What Changed | Direction-preserving Change label plus exact before → after summary |
| Membership addition | `Membership: Added` |
| Membership removal | Unranked historical row with `Membership: Removed` |
| Caveats | Visible universe-level warnings above the table |
| Evidence references | Reference count plus retained reference/source identities in the view model |

Current ranked rows stay in their original order. Removed members have no current rank and
appear after the ranked population; they cannot affect ranking.

## Filter semantics

Compact filters support current profile, Leader, Laggard, Attention, Changed, Added, Removed,
search, trend, momentum, and volatility. Filters only subset the already ordered comparison
rows. Reset clears every comparison filter and restores the full view. The current-state
technical filters remain secondary to the intelligence and membership filters.

## Membership change versus technical change

Membership and technical state are independent dimensions. A newly added weak member is
shown as:

- Profile: Weak
- Membership: Added
- Change: No prior comparable member state

It is not labeled as weakened unless a deterministic technical change event supports that
meaning. Removed members show no current technical state. Limited or unavailable comparison
history is stated in Status rather than converted into a performance conclusion.

## Summary, detail, and empty states

Current Read exposes comparison status and counts without repeating member cards. Important
caveats remain visible; the complete snapshot/comparison identity remains available in the
adjacent context expander. First observations use `First observation`; absent baselines use
`No baseline`; non-comparable intervals use `Not comparable`; comparable unchanged members
use `No material change`.

Company detail retains the existing deterministic explanation and factor content and renders
directly below the selected comparison row. Removed historical rows do not open current-company
detail.

## Forward compatibility

The consolidation preserves stable snapshot, member, event, evidence, and presentation source
identities. Future longitudinal observations can add presentation facts without changing the
table's ranking authority. Morning Coffee can consume the same deterministic artifacts later;
this work does not modify Morning Coffee or establish a new interpretation contract.
