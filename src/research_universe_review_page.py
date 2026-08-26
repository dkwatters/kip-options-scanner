"""User-centered Streamlit renderer for the canonical Research Universe model."""
from __future__ import annotations

from dataclasses import dataclass, replace
from hashlib import sha256
from typing import Callable

import pandas as pd
import streamlit as st

from src.navigation import request_navigation
from src.research_universe import (
    CandidateDisposition,
    IdentityStatus,
    ResearchUniverse,
    ResearchUniverseReviewService,
    UniverseState,
    trusted_promotion_reference,
)
from src.research_universe_repository import research_universe_repository_from_env
from src.research_universe_input import ResearchUniverseInputService, configured_research_universe_input_service
from src.research_universe_analysis import execute_research_universe_analysis, preflight_research_universe
from src.research_universe_diagnostics import ResearchUniverseDiagnosticStore
from src.technical_observation_service import configured_technical_observation_repositories
from src.tradier_client import TradierClient
from src.universe_analysis_snapshot_repository import (
    universe_analysis_snapshot_repository_from_env,
)
from src.universe_analysis_snapshot_service import (
    persist_completed_universe_analysis_snapshot,
)

GENERAL_USER_MODE = "general_user"
CURATOR_MODE = "curator"


class _UnavailableMarketDataClient:
    def __init__(self, error: Exception):
        self.error = error

    def get_price_history(self, *args, **kwargs):
        raise self.error


@dataclass(frozen=True, slots=True)
class ReviewRow:
    matching_key: str
    included: bool
    company: str
    ticker: str
    starting_company: bool
    rce_suggestion: bool
    disposition: str
    rank: int | None


def review_rows(universe: ResearchUniverse) -> tuple[ReviewRow, ...]:
    return tuple(ReviewRow(
        row.normalized_matching_key,
        row.disposition == CandidateDisposition.INCLUDED,
        row.company_name,
        row.ticker_or_identifier or "—",
        row.in_starting_companies,
        row.in_rce_suggestions,
        row.disposition.value,
        row.rce_rank,
    ) for row in universe.candidates)


def curator_diagnostics_visible(mode: str) -> bool:
    return mode == CURATOR_MODE


def _company_table(rows) -> pd.DataFrame:
    return pd.DataFrame([{
        "Company": row.company_name,
        "Ticker or identifier": row.ticker_or_identifier or "Unresolved",
        "Status": "Ready" if row.identity_status == IdentityStatus.RESOLVED else "Identity unresolved",
    } for row in rows])


def _suggestion_selection_key(key_prefix: str, suggestions) -> str:
    """Identify selection state by both its generation and ordered candidates."""
    generation = st.session_state.get(f"{key_prefix}_suggestion_selection_generation", 0)
    identity = "\0".join(row.normalized_matching_key for row in suggestions)
    fingerprint = sha256(identity.encode("utf-8")).hexdigest()[:12]
    return f"{key_prefix}_suggestions_{generation}_{fingerprint}"


def _selected_suggestions(suggestions, selected_rows) -> tuple:
    """Resolve one selection snapshot without partially applying stale indexes."""
    indexes = tuple(selected_rows)
    if any(
        isinstance(index, bool) or not isinstance(index, int) or index < 0 or index >= len(suggestions)
        for index in indexes
    ):
        return ()
    return tuple(suggestions[index] for index in indexes)


def _invalidate_suggestion_selection(key_prefix: str) -> None:
    generation_key = f"{key_prefix}_suggestion_selection_generation"
    st.session_state[generation_key] = st.session_state.get(generation_key, 0) + 1


def candidate_identity_validation_status(candidate) -> str | None:
    """Read new validation metadata while preserving legacy RCE compatibility."""
    metadata = candidate.rce_metadata
    validation = metadata.get("candidate_identity_validation", {})
    status = (
        validation.get("validation_status")
        if isinstance(validation, dict) else None
    )
    status = status or metadata.get("identity_validation_status")
    if status:
        return str(status)
    legacy = metadata.get("validation_status")
    if legacy:
        return "valid" if legacy == "valid" else "unresolved"
    return None


def candidate_promotion_eligible(candidate) -> bool:
    status = candidate_identity_validation_status(candidate)
    return status is None or status in {"valid", "corrected"}


def promote_suggested_candidate(
    universe: ResearchUniverse,
    matching_key: str,
    input_service: ResearchUniverseInputService,
) -> ResearchUniverse:
    """Include a suggestion, validating its supplied ticker through the manual path."""
    review_service = ResearchUniverseReviewService()
    candidate = next(
        (row for row in universe.candidates if row.normalized_matching_key == matching_key),
        None,
    )
    if candidate and not candidate_promotion_eligible(candidate):
        return universe
    if candidate is None or not candidate.in_rce_suggestions or not candidate.ticker_or_identifier:
        return review_service.revise(
            universe, dispositions={matching_key: CandidateDisposition.INCLUDED.value},
        )
    known_records = tuple(
        record for row in universe.candidates for record in row.source_records
    )
    _, promoted_records = input_service.resolve(
        candidate.ticker_or_identifier,
        source_reference=f"session:{universe.universe_id}:suggestion-promotion",
        known_records=known_records,
    )
    candidate_identity = candidate.rce_metadata.get("candidate_identity")
    promotion_validation_result = (
        candidate_identity_validation_status(candidate) or "valid"
    )
    original_records = tuple(
        record for record in candidate.source_records
        if record.source.value == "rce_generated"
        and record.metadata.get("candidate_identity") == candidate_identity
        and record.source_reference
    )
    promoted_records = tuple(
        replace(
            record,
            company_name=(
                candidate.company_name
                if record.identity_status != IdentityStatus.RESOLVED
                else record.company_name
            ),
            original_input=(
                candidate.original_input or candidate.company_name
                if record.identity_status != IdentityStatus.RESOLVED
                else record.original_input
            ),
            metadata={
                **dict(record.metadata),
                "identity_validation_status": (
                    promotion_validation_result
                    if record.identity_status == IdentityStatus.RESOLVED
                    else "unresolved"
                ),
                "candidate_identity_validation": candidate.rce_metadata.get(
                    "candidate_identity_validation", {}
                ),
                "membership_provenance": [
                    *candidate.rce_metadata.get("membership_provenance", []),
                    {
                        "source": "promoted_candidate",
                        "source_identity": candidate.rce_metadata.get("candidate_identity"),
                        "source_reference": record.source_reference,
                    },
                ],
                "discovery_lenses": candidate.rce_metadata.get("discovery_lenses", []),
                "evidence_references": candidate.rce_metadata.get("evidence_references", []),
                "candidate_identity": candidate.rce_metadata.get("candidate_identity"),
                **(
                    {
                        "trusted_promotion_reference": trusted_promotion_reference(
                            original_records[0],
                            replace(
                                record,
                                metadata={
                                    **dict(record.metadata),
                                    "identity_validation_status": (
                                        promotion_validation_result
                                    ),
                                },
                            ),
                            candidate_identity=str(candidate_identity),
                            validation_result=promotion_validation_result,
                        )
                    }
                    if len(original_records) == 1
                    and candidate.rce_metadata.get("candidate_identity")
                    else {}
                ),
            },
        )
        for record in promoted_records
    )
    if promoted_records:
        return review_service.revise(
            universe, additional_starting_companies=promoted_records,
        )
    return review_service.revise(
        universe, dispositions={matching_key: CandidateDisposition.INCLUDED.value},
    )


def render_research_universe_review(
    universe: ResearchUniverse,
    *,
    mode: str = GENERAL_USER_MODE,
    on_disposition: Callable[[str, str], None] | None = None,
    on_add_manual: Callable[[str], None] | None = None,
    on_analyze_universe: Callable[[], None] | None = None,
    preflight=None,
    on_continue_analysis: Callable[[], None] | None = None,
    analyze_company: Callable[[str], None] | None = None,
    key_prefix: str = "research_universe",
) -> None:
    st.caption("Research Universe")
    st.title(universe.title or "Untitled Research Universe")
    if universe.research_question:
        st.write(f'“{universe.research_question}”')
    else:
        st.caption("No original question was recorded.")

    handoff = universe.downstream_handoff()
    suggestions = tuple(
        row for row in universe.candidates
        if row.in_rce_suggestions and row.disposition == CandidateDisposition.PENDING
    )
    st.subheader("Summary")
    summary_parts = []
    if handoff.total_member_count:
        summary_parts.append(f"{handoff.total_member_count} companies included")
    if suggestions:
        summary_parts.append(f"{len(suggestions)} suggestions to review")
    if universe.established_topic:
        summary_parts.append(f"Established topic: {universe.established_topic}")
    st.caption(" · ".join(summary_parts) or "Ready for you to establish membership.")
    if universe.provenance.get("provider_error"):
        st.warning("Suggestions are temporarily unavailable. You can still add companies you know.")

    st.header("Universe Members")
    current = universe.approved_membership
    with st.container(border=True):
        if current:
            member_event = st.dataframe(
                _company_table(current), hide_index=True, on_select="rerun",
                selection_mode="multi-row", key=f"{key_prefix}_current_{universe.version}",
            )
            selected_members = tuple(current[index] for index in member_event.selection.rows)
            if st.button(
                "Remove selected", disabled=not selected_members or on_disposition is None,
                key=f"{key_prefix}_remove",
            ):
                st.session_state[f"{key_prefix}_confirm_remove"] = tuple(
                    row.normalized_matching_key for row in selected_members
                )
            pending_remove = st.session_state.get(f"{key_prefix}_confirm_remove", ())
            if pending_remove:
                st.warning(f"Remove {len(pending_remove)} selected company or companies?")
                with st.container(horizontal=True):
                    if st.button("Confirm removal", type="primary", key=f"{key_prefix}_confirm_remove_action"):
                        for key in pending_remove:
                            on_disposition(key, CandidateDisposition.REJECTED.value)
                        st.session_state.pop(f"{key_prefix}_confirm_remove", None)
                        st.rerun()
                    if st.button("Cancel", key=f"{key_prefix}_cancel_remove"):
                        st.session_state.pop(f"{key_prefix}_confirm_remove", None)
                        st.rerun()
        elif suggestions:
            st.info(
                "We identified companies that may belong in this Research Universe. "
                "Review them below and choose which companies to include."
            )
        else:
            st.caption("Add companies below to establish this Research Universe.")

        st.write("When this membership looks right, continue to analyze the universe.")
        if st.button(
            "Analyze Universe", type="primary", icon=":material/analytics:",
            disabled=handoff.total_member_count == 0,
            help="Validate the exact current membership before analysis.",
            key=f"{key_prefix}_analyze_all",
        ) and on_analyze_universe:
            on_analyze_universe()

        if preflight is not None:
            st.subheader("Confirm analysis")
            st.write(f"{preflight.handoff.total_member_count} universe members")
            st.write(f"{len(preflight.analyzable_tickers)} ready for analysis")
            st.write(f"{len(preflight.blocked)} needs attention")
            for entry in preflight.blocked:
                st.warning(f"{entry.ticker_or_identifier or entry.company_name} — {entry.reason}")
            with st.container(horizontal=True):
                if st.button(
                    "Continue with analyzable members", type="primary",
                    disabled=not preflight.analyzable_tickers,
                    key=f"{key_prefix}_continue_analysis",
                ) and on_continue_analysis:
                    on_continue_analysis()
                if st.button("Return to Research Universe", key=f"{key_prefix}_cancel_analysis"):
                    st.session_state.pop("active_universe_analysis_preflight", None)
                    st.rerun()

        st.subheader("Suggested Companies")
        st.caption("Choose which recommendations belong in your universe.")
        if suggestions:
            event = st.dataframe(
                pd.DataFrame([{
                    "Company": row.company_name,
                    "Ticker": row.ticker_or_identifier or "Unresolved",
                    "Why it may belong": row.rce_metadata.get("inclusion_rationale") or "Possible fit for this research topic",
                    "Discovery Lenses": ", ".join(row.rce_metadata.get("discovery_lenses", ())) or "Not provided",
                    "Related seeds": len(row.rce_metadata.get("related_seed_member_identities", ())),
                    "Evidence": len(row.rce_metadata.get("evidence_references", ())),
                    "Identity status": candidate_identity_validation_status(row) or "unresolved",
                    "Duplicate status": str(
                        row.rce_metadata.get("duplicate_status") or "not reported"
                    ).replace("_", " ").capitalize(),
                } for row in suggestions]),
                hide_index=True, on_select="rerun", selection_mode="multi-row",
                key=_suggestion_selection_key(key_prefix, suggestions),
            )
            selected = _selected_suggestions(suggestions, event.selection.rows)
            with st.container(horizontal=True):
                add_clicked = st.button(
                    "Add Selected", type="primary", icon=":material/add:",
                    disabled=(
                        not selected or on_disposition is None
                        or any(not candidate_promotion_eligible(row) for row in selected)
                    ),
                    key=f"{key_prefix}_add_selected",
                )
                reject_clicked = st.button(
                    "Reject", icon=":material/block:",
                    disabled=not selected or on_disposition is None,
                    key=f"{key_prefix}_reject_selected",
                )
                st.button("Leave Pending", disabled=not selected, key=f"{key_prefix}_leave_pending")
            if add_clicked or reject_clicked:
                disposition = CandidateDisposition.INCLUDED.value if add_clicked else CandidateDisposition.REJECTED.value
                for candidate in selected:
                    on_disposition(candidate.normalized_matching_key, disposition)
                _invalidate_suggestion_selection(key_prefix)
                st.rerun()
            if selected:
                candidate = selected[0]
                with st.expander("Suggestion details", icon=":material/info:"):
                    st.write(candidate.rce_metadata.get("inclusion_rationale") or "No detailed reason is stored for this suggestion.")
                    st.caption(f"Category or role: {candidate.rce_metadata.get('category') or 'Not provided'}")
                    st.caption("Discovery Lenses: " + (", ".join(candidate.rce_metadata.get("discovery_lenses", ())) or "Not provided"))
                    st.caption(f"Related seed companies: {len(candidate.rce_metadata.get('related_seed_member_identities', ())) }")
                    evidence = candidate.rce_metadata.get("evidence_references", ())
                    if evidence:
                        st.write("Evidence/support")
                        for reference in evidence:
                            st.caption(str(reference))
                    validation = candidate.rce_metadata.get("candidate_identity_validation", {})
                    raw_name = candidate.rce_metadata.get("raw_company_name")
                    raw_ticker = candidate.rce_metadata.get("raw_ticker_or_identifier")
                    if raw_name or raw_ticker:
                        st.caption(
                            f"Raw identity: {raw_name or 'Not provided'} / "
                            f"{raw_ticker or 'No ticker'}"
                        )
                        st.caption(
                            f"Validated identity: {candidate.company_name} / "
                            f"{candidate.ticker_or_identifier or 'Unresolved'}"
                        )
                    st.caption(
                        "Duplicate status: "
                        + str(candidate.rce_metadata.get("duplicate_status") or "not reported")
                        .replace("_", " ")
                        .capitalize()
                    )
                    st.write(
                        "Identity validation: "
                        + (candidate_identity_validation_status(candidate) or "unresolved")
                    )
                    if validation.get("correction_applied"):
                        st.caption(validation.get("correction_reason") or "Identity correction applied.")
                    if validation.get("unresolved_reason"):
                        st.warning(validation["unresolved_reason"])
        else:
            st.caption("There are no active suggestions to review.")

        rejected = tuple(row for row in universe.candidates if row.disposition == CandidateDisposition.REJECTED)
        if rejected:
            with st.expander(f"Rejected ({len(rejected)})"):
                st.dataframe(_company_table(rejected), hide_index=True)

        st.subheader("Add Companies")
        st.caption("Enter ticker symbols separated by commas to add them directly to this Research Universe.")
        with st.form(f"{key_prefix}_manual_add", border=False):
            raw = st.text_area(
                "Ticker symbols",
                placeholder="CRWD, PANW, ZS",
                help="Enter ticker symbols separated by commas.",
                key=f"{key_prefix}_manual_input",
            )
            submitted = st.form_submit_button(
                "Add Companies", icon=":material/add:", disabled=on_add_manual is None,
            )
        if submitted and on_add_manual:
            _invalidate_suggestion_selection(key_prefix)
            on_add_manual(raw)

    if curator_diagnostics_visible(mode):
        st.caption("Curator mode: publication, certification, and evaluation controls remain in Curator Tools.")


def render_current_research_universe_page(*, analyze_company=None) -> None:
    universe = st.session_state.get("current_research_universe")
    if universe is None:
        st.title("Research Universe")
        st.info("Start at Research Launchpad to build a Research Universe.")
        return

    service = ResearchUniverseReviewService()

    def save_current(universe: ResearchUniverse) -> None:
        research_universe_repository_from_env().save(universe)
        st.session_state.current_research_universe = universe

    def set_disposition(key: str, disposition: str) -> None:
        st.session_state.pop("active_universe_analysis_preflight", None)
        current = st.session_state.current_research_universe
        if disposition == CandidateDisposition.INCLUDED.value:
            revised = promote_suggested_candidate(
                current, key, configured_research_universe_input_service(),
            )
            save_current(revised)
            promoted = next((row for row in revised.candidates if row.normalized_matching_key == key), None)
            ResearchUniverseDiagnosticStore().append(
                "suggestion_promoted",
                request_run_id=str(current.provenance.get("request_run_id") or "unavailable"),
                universe_id=current.universe_id,
                universe_version=current.version,
                payload={
                    "matching_key": key,
                    "company_name": promoted.company_name if promoted else None,
                    "ticker": promoted.ticker_or_identifier if promoted else None,
                    "identity_resolution": promoted.identity_status.value if promoted else "candidate missing",
                    "disposition": promoted.disposition.value if promoted else disposition,
                },
            )
            return
        save_current(service.revise(current, dispositions={key: disposition}))

    def add_manual(raw: str) -> None:
        known_records = tuple(
            record for candidate in st.session_state.current_research_universe.candidates
            for record in candidate.source_records
        )
        parsed, records = configured_research_universe_input_service().resolve(
            raw,
            source_reference=f"session:{universe.universe_id}:manual-addition",
            known_records=known_records,
        )
        if parsed.invalid_values:
            st.warning("Ticker symbols are required. Check: " + ", ".join(parsed.invalid_values))
        if records:
            st.session_state.pop("active_universe_analysis_preflight", None)
            save_current(service.revise(
                st.session_state.current_research_universe,
                additional_starting_companies=records,
            ))
            st.session_state.pop(f"current_universe_{universe.universe_id}_v{universe.version}_manual_input", None)
            st.rerun()
        else:
            st.warning("Enter at least one ticker symbol.")

    def analyze_universe() -> None:
        try:
            client = TradierClient()
        except Exception as error:
            client = _UnavailableMarketDataClient(error)
        st.session_state.active_universe_analysis_preflight = preflight_research_universe(
            st.session_state.current_research_universe.downstream_handoff(), client,
        )
        st.rerun()

    def continue_analysis() -> None:
        preflight_state = st.session_state.active_universe_analysis_preflight
        current_handoff = st.session_state.current_research_universe.downstream_handoff()
        current_identity = tuple(
            (row.matching_key, row.ticker_or_identifier, row.identity_status)
            for row in current_handoff.ordered_members
        )
        preflight_identity = tuple(
            (row.matching_key, row.ticker_or_identifier, row.identity_status)
            for row in preflight_state.handoff.ordered_members
        )
        if (
            current_handoff.universe_id != preflight_state.handoff.universe_id
            or current_handoff.universe_version != preflight_state.handoff.universe_version
            or current_identity != preflight_identity
        ):
            st.session_state.pop("active_universe_analysis_preflight", None)
            st.error("Research Universe membership changed. Run Analyze Universe again to validate the current membership.")
            return
        repository, signal_repository = configured_technical_observation_repositories()
        repository.initialize()
        analysis_run = execute_research_universe_analysis(
            preflight_state, client=TradierClient(), repository=repository,
            signal_repository=signal_repository,
        )
        st.session_state.active_universe_analysis_run = analysis_run
        st.session_state.pop("active_universe_analysis_snapshot_id", None)
        st.session_state.pop("active_universe_analysis_snapshot_persistence_error", None)
        try:
            snapshot = persist_completed_universe_analysis_snapshot(
                handoff=preflight_state.handoff,
                run=analysis_run,
                observation_repository=repository,
                snapshot_repository=universe_analysis_snapshot_repository_from_env(),
            )
            st.session_state.active_universe_analysis_snapshot_id = snapshot.snapshot_id
            current = st.session_state.current_research_universe
            save_current(replace(
                current.with_state(UniverseState.ANALYZED),
                analysis_references=tuple(dict.fromkeys(
                    (*current.analysis_references, snapshot.snapshot_id)
                )),
            ))
        except Exception as error:
            # The reconciled current run remains valid and displayable.  Only its
            # durable historical record failed, which must remain explicit.
            st.session_state.active_universe_analysis_snapshot_persistence_error = str(error)
        ResearchUniverseDiagnosticStore().append(
            "analysis_ledger_finalized",
            request_run_id=str(st.session_state.current_research_universe.provenance.get("request_run_id") or analysis_run.scan_id),
            universe_id=analysis_run.universe_id,
            universe_version=analysis_run.universe_version,
            payload={
                "analysis_run_id": analysis_run.scan_id,
                "ledger": analysis_run.ledger,
            },
        )
        st.session_state.active_universe_analysis_handoff = preflight_state.handoff
        for key in (
            "tam_ticker_search", "tam_tickers", "tam_trend_states",
            "tam_momentum_states", "tam_volatility_states", "tam_scan_id",
            "tam_latest_scan_only", "tam_browse_historical_scans",
        ):
            st.session_state.pop(key, None)
        request_navigation("Universe Analysis")

    render_research_universe_review(
        universe,
        on_disposition=set_disposition,
        on_add_manual=add_manual,
        on_analyze_universe=analyze_universe,
        preflight=st.session_state.get("active_universe_analysis_preflight"),
        on_continue_analysis=continue_analysis,
        analyze_company=analyze_company,
        key_prefix=f"current_universe_{universe.universe_id}_v{universe.version}",
    )
