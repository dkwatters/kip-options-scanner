"""Question-led Streamlit presentation for the read-only Benchmark Explorer."""
from __future__ import annotations

from dataclasses import asdict
import logging
import os
from pathlib import Path
import re
from typing import Callable

import pandas as pd
import streamlit as st

from src.rce_benchmark_explorer_service import RCEBenchmarkExplorerService

LOGGER = logging.getLogger(__name__)

@st.cache_resource
def _service(root: str) -> RCEBenchmarkExplorerService:
    project = Path(root)
    return RCEBenchmarkExplorerService(
        baseline_path=project / "data/research/rce_benchmark_baseline_v0.1.1.json",
        fixture_dir=project / "tests/fixtures/rce_benchmarks",
        source_corpus_path=project / "data/research/rce_authored_source_corpus_v0.1.json",
        scoring_config_path=project / "config/rce_benchmark_scoring_v0.1.json",
        database_path=project / "data/research/rce_benchmarks.sqlite",
        curator_approval_path=os.getenv(
            "RCE_CURATOR_APPROVAL_PATH",
            str(project / "data/research/rce_benchmark_curator_approvals_v0.1.json"),
        ),
    )


def _display(value: object) -> object:
    return "—" if value is None or value == "" else value


def _frame(rows: list[dict[str, object]], *, empty: str = "None recorded.") -> None:
    if rows:
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    else:
        st.caption(empty)


def _candidate_rows(candidates) -> list[dict[str, object]]:
    return [{
        "Company": row.company_name, "Ticker": _display(row.ticker),
        "Expected classification": _display(row.expected_classification),
        "Returned or missing": "Returned" if row.returned else "Missing",
        "Rank": str(row.returned_rank) if row.returned_rank is not None else "—",
        "Expected category": _display(row.expected_category), "Returned category": _display(row.returned_category),
        "Category match": row.category_match, "Listing validity": row.listing_valid,
        "Public-status validity": row.public_status_valid, "Validation status": row.validation_status,
        "Comparison outcome": row.comparison_outcome, "Rationale field present": row.rationale_present,
        "Structured evidence field present": row.evidence_present,
        "Reviewer status": _display(row.reviewer_status),
    } for row in candidates]


def _attention_rows(rows) -> list[dict[str, object]]:
    return [{
        "Company": row.company_name,
        "Ticker": _display(row.ticker),
        "Expected category": _display(row.expected_category),
        "Returned category": _display(row.returned_category),
        "Category match": row.category_match,
        "Reviewer status": _display(row.reviewer_status),
        "Benchmark consequence": row.score_consequence,
    } for row in rows]


def _review_status(value: str | None) -> str:
    return "Needs review" if value in (None, "needs_verification") else value.replace("_", " ").capitalize()


def _render_investigation_candidate(row, *, index: int) -> None:
    with st.container(border=True):
        identity, category, status = st.columns([2, 2, 1], vertical_alignment="center")
        with identity:
            st.markdown(f"**{row.company_name}**")
            st.caption(f"Ticker: {_display(row.ticker)}")
        with category:
            st.caption("Returned category")
            st.write(_display(row.returned_category))
        with status:
            st.badge(
                _review_status(row.reviewer_status), icon=":material/rate_review:",
                color="orange" if row.reviewer_status in (None, "needs_verification") else "gray",
            )
        st.caption("Benchmark consequence")
        st.write(row.score_consequence)
        with st.container(horizontal=True):
            st.button("Compare", key=f"compare_{index}", icon=":material/compare_arrows:", disabled=True)
            st.button("Launch analysis", key=f"analysis_{index}", icon=":material/open_in_new:", disabled=True)
            st.button("Consider for benchmark", key=f"consider_{index}", icon=":material/add_task:", disabled=True)


def _render_metric_contributions(metrics) -> None:
    for row in metrics:
        percentage = max(0.0, min(1.0, row.raw_value))
        with st.container(border=True):
            label, value = st.columns([4, 1], vertical_alignment="center")
            with label:
                st.markdown(f"**{row.display_name}**")
                st.caption(row.plain_language_explanation)
            with value:
                st.metric("Metric result", f"{percentage:.0%}", label_visibility="collapsed")
            st.progress(percentage, text=f"Contribution to overall score: {row.weighted_contribution:.4f}")


def _render_reviewed_benchmark(reviewed) -> None:
    if reviewed is None:
        st.warning("The canonical fixture is missing; reviewed expectations and provenance are unavailable.")
        return
    st.write(reviewed.description or "No description recorded.")
    st.markdown("**Expected candidates, classifications, categories, importance, and notes**")
    _frame([{
        "Company": row.get("company_name"), "Ticker": row.get("ticker"),
        "Classification": row.get("expectation"), "Expected category": row.get("category_name"),
        "Importance": row.get("importance"), "Role": row.get("role_summary"),
        "Evidence summary": row.get("evidence_summary"), "Notes": row.get("notes"),
    } for row in reviewed.expected_candidates])
    st.markdown("**Expected categories**")
    _frame([dict(row) for row in reviewed.expected_categories])
    st.markdown("**Explicit exclusions**")
    _frame([dict(row) for row in reviewed.exclusions], empty="No explicit must-exclude securities recorded.")
    st.markdown("**Notes and caveats**")
    st.write(reviewed.review_notes or "No review notes recorded.")
    for caveat in reviewed.caveats:
        st.warning(caveat)


OUTCOME_LABELS = {
    "agreement": "Agreement - present in both corpora",
    "authored_only": "Authored only - not returned by RCE",
    "rce_only": "RCE discovery not present in the authored source corpus",
    "identity_review": "Identity review - ambiguous deterministic match",
}


def _status_color(value: object) -> str:
    text = str(value)
    if "Appears in both corpora" in text:
        return "background-color: #d1fae5; color: #064e3b"
    if "Appears only in this corpus" in text:
        return "background-color: #fee2e2; color: #7f1d1d"
    if "Identity requires review" in text:
        return "background-color: #fef3c7; color: #78350f"
    return ""


def _comparison_frame(rows: list[dict[str, object]], *, empty: str) -> None:
    if not rows:
        st.caption(empty)
        return
    frame = pd.DataFrame(rows)
    styled = frame.style.map(_status_color, subset=["Company"])
    st.dataframe(styled, hide_index=True, width="stretch")


def _select_investigation(row, side: str) -> None:
    st.session_state.benchmark_investigation_key = row.normalized_matching_key
    st.session_state.benchmark_investigation_side = side


@st.dialog("Add to Benchmark of Record?", icon=":material/add_task:", on_dismiss="rerun")
def _confirm_benchmark_inclusion(service, benchmark_id: str, row) -> None:
    if st.session_state.pop("benchmark_approval_close_dialog", False):
        st.rerun()
    st.write(f"Add **{row.company_name}** ({_display(row.ticker_or_identifier)}) to this Benchmark of Record?")
    st.caption("This records a curator approval. It does not change the authored corpus or stored RCE result.")
    approval_error = st.session_state.pop("benchmark_approval_error", None)
    if approval_error:
        st.error(approval_error)
    with st.container(horizontal=True):
        st.button(
            "Confirm addition", type="primary", icon=":material/check:",
            key=f"confirm_bor_{benchmark_id}_{row.normalized_matching_key}",
            on_click=_approve_benchmark_inclusion,
            args=(service, benchmark_id, row),
        )
        if st.button("Cancel", key=f"cancel_bor_{benchmark_id}_{row.normalized_matching_key}"):
            st.rerun()


def _approve_benchmark_inclusion(service, benchmark_id: str, row) -> None:
    try:
        service.approve_for_benchmark_of_record(benchmark_id, row.normalized_matching_key)
    except (OSError, RuntimeError, ValueError) as error:
        st.session_state.benchmark_approval_error = str(error)
    else:
        st.session_state.benchmark_approval_success = row.company_name
        st.session_state.benchmark_approval_close_dialog = True


def _sam_compatible_ticker(value: str | None) -> str | None:
    ticker = (value or "").strip().upper()
    return ticker if re.fullmatch(r"[A-Z][A-Z0-9.]{0,9}", ticker) else None


def _render_selection_actions(
    service, comparison, row, side: str, analyze_company: Callable[[str], None] | None,
) -> None:
    if row is None:
        return
    approved = row.normalized_matching_key in service.approved_matching_keys(comparison.benchmark_id)
    if row.comparison_outcome == "agreement":
        st.success("Included automatically in the Benchmark of Record by corpus agreement.")
    elif approved:
        st.success("Included in the Benchmark of Record by curator approval.")
    else:
        if st.button(
            "Add to Benchmark of Record", type="primary", icon=":material/add_task:",
            key=f"add_bor_{side}_{comparison.benchmark_id}_{row.normalized_matching_key}",
        ):
            _confirm_benchmark_inclusion(service, comparison.benchmark_id, row)
    ticker = _sam_compatible_ticker(row.ticker_or_identifier)
    with st.container(horizontal=True):
        st.button(
            "Analyze Company", disabled=ticker is None or analyze_company is None,
            key=f"analyze_selection_{side}_{comparison.benchmark_id}_{row.normalized_matching_key}",
            on_click=analyze_company, args=(ticker or "",), icon=":material/analytics:",
        )
        st.button(
            "Investigate", key=f"investigate_{side}_{comparison.benchmark_id}_{row.normalized_matching_key}",
            on_click=_select_investigation, args=(row, side), icon=":material/search:",
        )
        if row.appears_in_authored_corpus:
            st.button(
                "View Source", key=f"source_{side}_{comparison.benchmark_id}_{row.normalized_matching_key}",
                on_click=_select_investigation, args=(row, side), icon=":material/description:",
            )
    if ticker is None:
        st.caption("SAM requires a compatible public ticker for analysis.")


def _render_corpus_comparison(
    comparison, service, analyze_company: Callable[[str], None] | None,
) -> None:
    st.subheader("Authored Source Corpus vs RCE Candidate Corpus")
    st.caption(
        f"Authored source {comparison.source_corpus_version} from {comparison.source_document}. "
        "Neither side is the Benchmark of Record."
    )
    with st.container(horizontal=True):
        st.metric("Authored companies", comparison.authored_unique_count, border=True)
        st.metric("Authored placements", comparison.authored_placement_count, border=True)
        st.metric("Stored RCE candidates", comparison.rce_candidate_count, border=True)
        st.metric("Identity review", comparison.identity_review_count, border=True)

    st.markdown(
        "**Comparison legend:** Green — appears in both corpora · "
        "Red — appears only in this corpus · Yellow — identity requires review"
    )

    by_name = {}
    for row in comparison.rows:
        if row.appears_in_authored_corpus:
            by_name[row.company_name.casefold()] = row
    left_rows = []
    for row in comparison.authored_candidates:
        result = by_name.get(row.company_name.casefold())
        outcome = result.comparison_outcome if result else "authored_only"
        left_rows.append({
            "Company": f"{row.company_name} — " + (
                "Appears in both corpora" if outcome == "agreement" else
                "Identity requires review" if outcome == "identity_review" else
                "Appears only in this corpus"
            ),
            "Ticker / identifier": _display(row.ticker_or_identifier),
            "Source page": row.source_page,
        })
    by_rank = {row.rce_rank: row for row in comparison.rows if row.appears_in_rce_corpus and row.rce_rank is not None}
    right_rows = []
    for row in comparison.rce_candidates:
        result = by_rank.get(row.returned_rank)
        outcome = result.comparison_outcome if result else "rce_only"
        right_rows.append({
            "Company": f"{row.company_name} — " + (
                "Appears in both corpora" if outcome == "agreement" else
                "Identity requires review" if outcome == "identity_review" else
                "Appears only in this corpus"
            ),
            "Ticker": _display(row.ticker),
            "Rank": str(row.returned_rank) if row.returned_rank is not None else "—",
        })

    left, right = st.columns(2)
    with left.container(border=True):
        st.markdown("#### Authored Source Corpus")
        st.caption("Complete primary company-table placements for this selected source document.")
        _comparison_frame(left_rows, empty="No authored primary constituents are available.")
        authored_options = tuple(row for row in comparison.rows if row.appears_in_authored_corpus)
        selected_authored = st.selectbox(
            "Company to investigate", authored_options, index=None,
            format_func=lambda row: f"{row.company_name} ({_display(row.ticker_or_identifier)})",
            key=f"authored_company_{comparison.benchmark_id}",
        )
        _render_selection_actions(
            service, comparison, selected_authored, "Authored Source Corpus", analyze_company,
        )
    with right.container(border=True):
        st.markdown("#### RCE Candidate Corpus")
        st.caption("Complete structured candidate list returned in the stored certified run.")
        _comparison_frame(right_rows, empty="No stored RCE candidates are available.")
        rce_options = tuple(row for row in comparison.rows if row.appears_in_rce_corpus)
        selected_rce = st.selectbox(
            "Company to investigate", rce_options, index=None,
            format_func=lambda row: f"{row.company_name} ({_display(row.ticker_or_identifier)})",
            key=f"rce_company_{comparison.benchmark_id}",
        )
        _render_selection_actions(
            service, comparison, selected_rce, "RCE Candidate Corpus", analyze_company,
        )

    with st.expander("Candidate comparison details", icon=":material/info:"):
        st.caption("Secondary metadata; category wording does not affect primary agreement.")
        _frame([{
            "Company": row.company_name,
            "Authored category": _display(row.authored_category),
            "RCE category": _display(row.rce_category),
            "Validation status": _display(row.validation_status),
            "Benchmark consequence": (
                "Authored candidate omitted from stored RCE candidates."
                if row.comparison_outcome == "authored_only" else "No primary comparison penalty."
            ),
            "Rationale field present": (
                "—" if row.rationale_present is None else "Yes" if row.rationale_present else "No"
            ),
            "Evidence field present": (
                "—" if row.evidence_present is None else "Yes" if row.evidence_present else "No"
            ),
            "Source page and notes": ", ".join(row.source_pages) or "—",
            "Identity-match explanation": row.explanation,
        } for row in comparison.rows])


def _render_company_investigation(investigation, analyze_company: Callable[[str], None] | None) -> None:
    st.subheader("Company investigation")
    with st.container(border=True):
        st.markdown(f"### {investigation.company_name}")
        st.caption(
            f"Ticker or identifier: {_display(investigation.ticker_or_identifier)} · "
            f"Selected benchmark: {investigation.benchmark_name} · "
            f"Selected from: {investigation.originating_side}"
        )
        st.badge(investigation.comparison_status)

        identity, comparison = st.columns(2)
        with identity:
            st.markdown("**Corpus comparison**")
            st.write(f"Present in authored source corpus: {'Yes' if investigation.appears_in_authored_corpus else 'No'}")
            st.write(f"Present in stored RCE candidate corpus: {'Yes' if investigation.appears_in_rce_corpus else 'No'}")
            st.write(f"RCE rank: {_display(investigation.rce_rank)}")
            st.write(f"Matching method: {investigation.matching_method}")
            st.info(investigation.explanation)
        with comparison:
            st.markdown("**Authored source evidence**")
            if investigation.source_evidence:
                _frame([{
                    "Original source section": row.source_section,
                    "Source document": row.source_document,
                    "Source page": row.source_page,
                    "Source notes": _display(row.source_notes),
                    "Duplicate placement": "Yes" if row.duplicate_placement else "No",
                    "Placement": row.placement_index,
                } for row in investigation.source_evidence])
            else:
                st.caption("Not present in the authored source corpus.")

        st.markdown("**RCE information**")
        if investigation.rce_candidate:
            row = investigation.rce_candidate
            _frame([{
                "Returned company name": row.company_name,
                "Returned ticker": _display(row.ticker),
                "Rank": _display(row.rank),
                "Returned category (metadata only)": _display(row.category_metadata),
                "Validation status": row.validation_status,
                "Rationale field present": "Yes" if row.rationale_present else "No",
                "Structured evidence field present": "Yes" if row.evidence_present else "No",
                "Benchmark consequence / evaluator interpretation": row.benchmark_consequence,
            }])
            st.caption(
                "The certified artifact records field-presence indicators; the full RCE narrative or "
                "rationale was not retained in this artifact."
            )
        else:
            st.caption("No stored RCE candidate information is available for this company.")

        st.markdown("**Comparison context**")
        st.caption("Other companies in this benchmark; this is comparison context, not definitive similarity.")
        _frame([{
            "Company": row.company_name,
            "Ticker / identifier": _display(row.ticker_or_identifier),
            "Comparison status": row.comparison_status,
        } for row in investigation.comparison_context])

        ticker = _sam_compatible_ticker(investigation.ticker_or_identifier)
        with st.container(horizontal=True):
            st.button(
                "Analyze Company", icon=":material/analytics:", disabled=ticker is None or analyze_company is None,
                key=f"analyze_{investigation.benchmark_id}_{ticker or investigation.company_name}",
                on_click=analyze_company, args=(ticker or "",),
            )
            st.button("Compare Similar Companies", disabled=True, icon=":material/compare_arrows:")
        if ticker is None:
            st.info("SAM requires one compatible public ticker; this entity cannot be handed to SAM as recorded.")
        st.caption("Compare Similar Companies is not yet available because no completed workflow exists.")


def _render_benchmark_of_record(service, benchmark_id: str) -> None:
    st.subheader("Benchmark of Record")
    st.caption(
        "Current read-only membership: corpus agreements plus companies explicitly approved by a curator."
    )
    members = service.benchmark_of_record(benchmark_id)
    _frame([{
        "Company": row.company_name,
        "Ticker": _display(row.ticker_or_identifier),
        "Source": row.inclusion_source,
    } for row in members], empty="No companies are currently included.")


def _curator_company_color(outcome: str) -> str:
    return {
        "agreement": "background-color: #d1fae5; color: #064e3b",
        "authored_only": "background-color: #fee2e2; color: #7f1d1d",
        "rce_only": "background-color: #fee2e2; color: #7f1d1d",
        "identity_review": "background-color: #fef3c7; color: #78350f",
    }.get(outcome, "")


def _render_provenance(investigation, inclusion_origin: str | None) -> None:
    with st.expander("View Provenance", icon=":material/history:"):
        st.write(f"Inclusion origin: {_display(inclusion_origin or 'Not yet included')}")
        if investigation.source_evidence:
            for source in investigation.source_evidence:
                st.write(f"Original source benchmark: {_display(source.source_document)}")
                st.write(f"Original category or section: {_display(source.source_section)}")
                st.write(f"Source page: {_display(source.source_page)}")
                st.write(f"Source note or rationale: {_display(source.source_notes)}")
        elif investigation.rce_candidate:
            st.write("RCE-discovery origin: stored certified RCE candidate corpus")
        else:
            st.caption("No source document provenance is retained for this record.")
        if inclusion_origin == "Curator approval":
            st.caption("The approval store does not retain curator identity or decision rationale.")


def _render_inline_curator_detail(service, comparison, row, side,
                                  analyze_company: Callable[[str], None] | None) -> None:
    investigation = service.company_investigation(
        comparison.benchmark_id, row.matching_key, originating_side=side,
    )
    if investigation is None:
        st.warning("The selected company is no longer available in this benchmark comparison.")
        return
    if investigation.comparison_outcome == "rce_only":
        st.markdown(f"#### Why did RCE surface {investigation.company_name}?")
        candidate = investigation.rce_candidate
        if candidate:
            st.write(f"Returned category (metadata): {_display(candidate.category_metadata)}")
            st.write(f"Returned rank: {_display(candidate.rank)}")
            st.write(f"Validation status: {_display(candidate.validation_status)}")
            st.write(f"Rationale field present: {'Yes' if candidate.rationale_present else 'No'}")
            st.write(f"Structured evidence present: {'Yes' if candidate.evidence_present else 'No'}")
            st.caption("The retained artifact records field-presence indicators; the full narrative was not retained.")
    else:
        st.markdown(f"#### Why is {investigation.company_name} here?")
        if investigation.source_evidence:
            source = investigation.source_evidence[0]
            st.write(f"Original benchmark category or section: {_display(source.source_section)}")
            st.write(source.source_notes or "No authored source note was retained.")
            st.caption(f"Source: {_display(source.source_document)} · page {_display(source.source_page)}")
        if investigation.comparison_outcome == "authored_only":
            st.write("RCE status: Not returned in the stored RCE candidate corpus.")
            st.caption("The retained artifact does not establish why it was omitted.")
        elif investigation.comparison_outcome == "identity_review":
            st.warning("Identity requires review before relying on the deterministic match.")
        else:
            st.caption("Included automatically because the independently authored and RCE corpora agree.")

    approved = row.matching_key in service.approved_matching_keys(comparison.benchmark_id)
    if row.comparison_outcome == "agreement":
        origin = "Agreement"
        st.success("Included automatically by corpus agreement.")
    elif approved:
        origin = "Curator approval"
        st.success("Included by curator approval.")
    else:
        origin = None
        if st.button("Add to Benchmark of Record", type="primary", icon=":material/add_task:",
                     key=f"inline_add_{side}_{comparison.benchmark_id}_{row.matching_key}"):
            comparison_row = next(item for item in comparison.rows
                                  if item.normalized_matching_key == row.matching_key)
            _confirm_benchmark_inclusion(service, comparison.benchmark_id, comparison_row)
    ticker = _sam_compatible_ticker(row.ticker)
    st.button("Analyze Company", disabled=ticker is None or analyze_company is None,
              key=f"inline_analyze_{side}_{comparison.benchmark_id}_{row.matching_key}",
              on_click=analyze_company, args=(ticker or "",), icon=":material/analytics:")
    if ticker is None:
        st.caption("SAM requires a compatible public ticker for analysis.")
    _render_provenance(investigation, origin)


def _render_curator_panel(service, comparison, side: str, title: str,
                          analyze_company: Callable[[str], None] | None) -> None:
    st.markdown(f"#### {title}")
    rows = service.curator_rows(comparison.benchmark_id, side)
    legend = ":green[■] Both corpora · :red[■] This corpus only"
    if any(row.comparison_outcome == "identity_review" for row in rows):
        legend += " · :yellow[■] Identity requires review"
    st.caption(f"{legend} · :material/check_box: Included in Benchmark of Record")
    values = [{"Included": row.included, "Company": row.company_name,
               "Ticker": _display(row.ticker), **({"Rank": row.rank} if side == "rce" else {})}
              for row in rows]
    if not values:
        st.caption("No corpus companies are available.")
        return
    frame = pd.DataFrame(values)
    outcomes = {row.company_name: row.comparison_outcome for row in rows}
    styled = frame.style.map(
        lambda value: _curator_company_color(outcomes.get(str(value), "")), subset=["Company"],
    )
    event = st.dataframe(
        styled, hide_index=True, width="stretch", on_select="rerun", selection_mode="single-row",
        key=f"{side}_curator_table_{comparison.benchmark_id}",
        column_config={"Included": st.column_config.CheckboxColumn("Included", disabled=True)},
    )
    if event.selection.rows:
        _render_inline_curator_detail(service, comparison, rows[event.selection.rows[0]], title, analyze_company)


def _render_inline_curator_workflow(service, comparison,
                                    analyze_company: Callable[[str], None] | None) -> None:
    progress = service.curator_progress(comparison.benchmark_id)
    st.caption(
        f"{progress.total_members} included · "
        f"{progress.pending_authored_only + progress.pending_rce_discoveries} pending decisions"
    )
    left, right = st.columns(2)
    with left.container(border=True):
        _render_curator_panel(service, comparison, "authored", "Authored Source Corpus", analyze_company)
    with right.container(border=True):
        _render_curator_panel(service, comparison, "rce", "RCE Candidate Corpus", analyze_company)
    st.markdown("#### Benchmark of Record summary")
    st.caption(
        f"{progress.total_members} included · {progress.agreements_included} automatic agreements · "
        f"{progress.curator_additions} curator additions · "
        f"{progress.pending_authored_only + progress.pending_rce_discoveries} one-sided companies remaining"
    )
    with st.expander("View Benchmark of Record", expanded=False, icon=":material/fact_check:"):
        _frame([{"Company": member.company_name, "Ticker": _display(member.ticker_or_identifier),
                 "Inclusion origin": member.inclusion_source}
                for member in service.benchmark_of_record(comparison.benchmark_id)],
               empty="No companies are currently included.")


def render_benchmark_explorer(
    root: Path, *, analyze_company: Callable[[str], None] | None = None,
) -> None:
    st.header("Benchmark curator workbench")
    try:
        service = _service(str(root))
        summary = service.run_summary()
        if not summary.available:
            st.error(summary.error_message or "The certified benchmark is unavailable.")
            return

        st.subheader("Choose a benchmark")
        selected = st.selectbox(
            "Benchmark domain",
            summary.domains,
            format_func=lambda row: row.benchmark_name,
            key="benchmark_curator_domain",
        )
        if st.session_state.get("benchmark_investigation_domain") != selected.benchmark_id:
            st.session_state.benchmark_investigation_domain = selected.benchmark_id
            st.session_state.pop("benchmark_investigation_key", None)
            st.session_state.pop("benchmark_investigation_side", None)
        detail = service.get_benchmark(selected.benchmark_id)
        if detail is None:
            st.warning("The selected benchmark is unavailable.")
            return

        st.markdown(f"### {detail.benchmark_name}")
        st.write(detail.question)

        comparison = service.corpus_comparison(selected.benchmark_id)
        if comparison.available:
            approved_company = st.session_state.pop("benchmark_approval_success", None)
            if approved_company:
                st.toast(f"{approved_company} added to the Benchmark of Record.", icon=":material/check:")
            _render_inline_curator_workflow(service, comparison, analyze_company)
        else:
            st.subheader("Authored Source Corpus vs RCE Candidate Corpus")
            st.warning(comparison.error_message or "Corpus comparison is unavailable.")

        with st.expander("RCE evaluation details", expanded=False, icon=":material/analytics:"):
            st.caption(
                f"Certified run: {summary.run_label} · Review state: {summary.review_state_label}. "
                "This is a certified snapshot, not a live review queue. "
                "Scores are deterministic benchmark results, not investment recommendations."
            )
            st.caption("Deterministic scoring and fixture outcomes; secondary to curator review.")
            expected_returned = detail.candidates_in_group("expected_returned")
            missing = detail.candidates_in_group("expected_missing")
            unexpected = detail.candidates_in_group("unexpected")
            violations = detail.candidates_in_group("must_exclude")
            _render_metric_contributions(detail.metrics)
            st.markdown("**Detailed metric table**")
            _frame([{
                "Metric": row.display_name,
                "What it means": row.plain_language_explanation,
                "Raw value": row.raw_value,
                "Weight": row.configured_weight,
                "Weighted contribution": row.weighted_contribution,
                "Calculation note": row.calculation_note,
            } for row in detail.metrics])

            st.markdown("**Unexpected, missing, and exclusion fixture outcomes**")
            _frame(_attention_rows((*unexpected, *missing, *violations)), empty="No fixture outcomes require attention.")
            st.markdown("**Evaluation fixture assumptions and expectations**")
            _render_reviewed_benchmark(detail.reviewed)

            st.markdown("**Developer diagnostics**")
            st.markdown("**Certified domain run inventory**")
            _frame([{
                "Benchmark name": row.benchmark_name, "Exact question": row.question,
                "Overall score": row.overall_score, "Execution Status": row.execution_status,
                "Benchmark version": row.benchmark_version, "Run label": row.run_label,
                "Certified-snapshot unresolved unexpected candidates": row.unresolved_unexpected_candidates,
            } for row in summary.domains])
            st.caption(
                f"Execution status: {detail.execution_status} · Benchmark {detail.benchmark_version} · "
                f"Run {detail.run_label} · Provider {detail.provider} · Model {detail.model} · "
                f"Prompt {detail.prompt_version} · Scoring configuration {detail.scoring_configuration_version}"
            )
            st.markdown("**Parser warnings and limitations**")
            if not detail.parser_warnings and not detail.limitations:
                st.caption("None recorded.")
            for warning in detail.parser_warnings:
                st.warning(warning)
            for limitation in detail.limitations:
                st.info(limitation)
            st.markdown("**Category comparison**")
            _frame([asdict(row) for row in detail.categories])
            st.markdown("**Complete candidate scorecard**")
            st.caption("Recorded evaluator fields only; there is no per-security quality score.")
            _frame(_candidate_rows(detail.candidates))
            if detail.reviewed is not None:
                st.markdown("**Sources and provenance**")
                _frame([dict(row) for row in detail.reviewed.sources])
                st.caption(
                    f"Reviewed by: {_display(detail.reviewed.reviewed_by)} · "
                    f"Source: {_display(detail.reviewed.source_document)} · "
                    f"Source date: {_display(detail.reviewed.source_date)}"
                )
            for diagnostic in service.diagnostics:
                st.warning(diagnostic)

            st.info("No benchmark data may be modified from this screen.")
    except Exception:
        LOGGER.exception("Unexpected Benchmark Explorer rendering error")
        st.error("Benchmark Explorer encountered an unexpected error. Details were written to the application log.")
