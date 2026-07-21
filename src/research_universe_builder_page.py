"""Research Launchpad inputs and session-only Research Universe creation."""
from __future__ import annotations

from pathlib import Path
import re
from uuid import uuid4

import streamlit as st

from src.navigation import request_navigation
from src.rce_benchmark_explorer_service import RCEBenchmarkExplorerService
from src.research_conversation import (
    ResearchConversationService,
    create_research_conversation_provider,
    research_conversation_confidence_threshold,
)
from src.research_universe import (
    ResearchUniverseReviewService,
    UniverseSource,
    UniverseType,
    source_record,
)
from src.research_universe_input import (
    ResearchUniverseInputService,
    configured_research_universe_input_service,
    parse_ticker_input,
)
from src.research_universe_diagnostics import ResearchUniverseDiagnosticStore, raw_provider_artifact


def readable_universe_title(topic_name: str | None, saved_title: str | None, question: str) -> str:
    """Derive a deterministic user-facing title without another model call."""
    base = (topic_name or saved_title or question or "").strip()
    if not base:
        return "Untitled Research Universe"
    concise = re.sub(r"\s+", " ", base).strip(" \t\r\n?.!")
    about_match = re.search(r"\b(?:about|around|covering)\s+(.+)$", concise, flags=re.IGNORECASE)
    if about_match and re.match(
        r"^(?:i(?:'d| would)? like|i want|tell me|help me|what|which|who|can you)",
        concise,
        flags=re.IGNORECASE,
    ):
        concise = about_match.group(1)
    concise = re.sub(
        r"^(?:please\s+)?(?:research|analyze|explore|identify|find|show me)\s+",
        "",
        concise,
        flags=re.IGNORECASE,
    )
    concise = re.sub(r"^(?:the\s+)?companies\s+(?:in|across|within)\s+", "", concise, flags=re.IGNORECASE)
    concise = re.split(r"[,;:]|\b(?:that|which|who)\b", concise, maxsplit=1, flags=re.IGNORECASE)[0]
    concise = re.sub(r"\s+(?:research\s+)?universe(?:\s+research\s+universe)*\s*$", "", concise, flags=re.IGNORECASE)
    concise = re.sub(r"\s+market\s*$", "", concise, flags=re.IGNORECASE)
    words = concise.split()
    if len(words) > 7:
        concise = " ".join(words[:7])
    concise = concise.strip(" \t\r\n?.!")
    if concise:
        concise = concise[0].upper() + concise[1:]
    return concise or "Untitled Research Universe"
from src.research_universe_builder import build_free_form_request, parse_anchor_companies
from src.universe import UniverseError, load_universe


LAUNCHPAD_WIDGET_KEYS = (
    "universe_builder_question",
    "universe_builder_anchors",
    "universe_builder_topic",
    "universe_builder_saved",
)


def start_new_research() -> None:
    """Reset only launchpad draft widgets; preserve navigation and saved/current work."""
    for key in LAUNCHPAD_WIDGET_KEYS:
        st.session_state.pop(key, None)
    st.session_state.pop("active_universe_analysis_handoff", None)
    st.session_state.pop("active_universe_analysis_preflight", None)
    st.session_state.pop("active_universe_analysis_run", None)
    st.session_state.pop("active_universe_analysis_snapshot_id", None)
    st.session_state.pop("active_universe_analysis_snapshot_persistence_error", None)
    request_navigation("Research Launchpad")


def established_topics(service: RCEBenchmarkExplorerService | None = None):
    """Expose the readable 17-topic catalog without benchmark language in the UI."""
    return (service or RCEBenchmarkExplorerService()).list_domains()


def _manual_records(raw: str, universe_id: str, *, known_records=(), use_market_data: bool = False):
    input_service = (
        configured_research_universe_input_service()
        if use_market_data else ResearchUniverseInputService()
    )
    return input_service.resolve(
        raw,
        source_reference=f"session:{universe_id}:manual",
        known_records=known_records,
    )[1]


def _topic_records(service: RCEBenchmarkExplorerService, topic_id: str):
    rows = service.authored_source_candidates(topic_id)
    return tuple(source_record(
        {
            "company_name": row.company_name,
            "ticker_or_identifier": row.ticker_or_identifier,
            "source_page": row.source_page,
            "source_section": row.source_section,
            "source_document": row.source_document,
            "source_corpus_version": row.source_corpus_version,
        },
        UniverseSource.CURATOR_AUTHORED,
        source_reference=(
            f"established-topic:{topic_id}:{row.source_document}:"
            f"{row.source_corpus_version}"
        ),
    ) for row in rows)


def _stored_suggestions(service: RCEBenchmarkExplorerService, topic_id: str):
    return tuple(source_record(
        {
            "company_name": row.company_name,
            "ticker": row.ticker,
            "rank": row.returned_rank,
            "category": row.returned_category,
            "validation_status": row.validation_status,
            "identity_status": "resolved" if row.validation_status == "valid" else "unresolved",
        },
        UniverseSource.RCE_GENERATED,
        source_reference=f"stored-rce:{topic_id}",
    ) for row in service.rce_corpus_candidates(topic_id))


def _known_identity_records(service: RCEBenchmarkExplorerService):
    """Project existing reviewed metadata into a deterministic identity catalog."""
    records = []
    for topic in service.list_domains():
        records.extend(_topic_records(service, topic.benchmark_id))
        records.extend(_stored_suggestions(service, topic.benchmark_id))
    return tuple(record for record in records if record.identity_status.value == "resolved")


def _saved_options(root: Path) -> tuple[Path, ...]:
    return tuple(
        path for path in sorted((root / "data").glob("*.csv"))
        if path.stem.casefold() != "universe_default"
    )


def _saved_records(path: Path | None, universe_id: str):
    if path is None:
        return ()
    try:
        rows = load_universe(str(path))
    except UniverseError:
        return ()
    return tuple(source_record(
        {"company_name": row.symbol, "ticker": row.symbol, "compatibility_csv": str(path)},
        UniverseSource.IMPORTED,
        source_reference=f"compatibility-csv:{path}",
    ) for row in rows)


def _provider_suggestions(question: str, starting_records, *, universe_id: str, diagnostic_store=None):
    anchors = parse_anchor_companies(",".join(
        record.ticker_or_identifier or record.company_name for record in starting_records
    ))
    request = build_free_form_request(question, anchors)
    provider = create_research_conversation_provider()
    response = ResearchConversationService(
        provider,
        confidence_threshold=research_conversation_confidence_threshold(),
    ).interpret_request(request)
    candidates = response.structured_response.get("candidate_securities", [])
    records = tuple(source_record(
        {
            **dict(row),
            "rank": index,
            "identity_status": (
                "resolved" if str(row.get("validation_status") or "").casefold() == "valid"
                else "unresolved"
            ),
        }, UniverseSource.RCE_GENERATED,
        source_reference="session:rce-suggestions",
    ) for index, row in enumerate(candidates, 1) if isinstance(row, dict))
    title = response.structured_response.get("suggested_research_universe_name")
    request_run_id = str(uuid4())
    (diagnostic_store or ResearchUniverseDiagnosticStore()).append(
        "rce_response_parsed",
        request_run_id=request_run_id,
        universe_id=universe_id,
        universe_version=1,
        payload={
            "request": {
                "original_question": request.original_question,
                "prompt_version": request.prompt_version,
                "request_timestamp": request.request_timestamp,
                "anchor_companies": request.anchor_companies,
                "request_origin": request.request_origin,
            },
            "raw_provider_response": raw_provider_artifact(response.raw_response),
            "parsed_candidates": [
                {"company_name": row.company_name, "ticker": row.ticker_or_identifier}
                for row in records
            ],
            "provider_diagnostics": response.metadata.diagnostics(),
        },
    )
    return records, title, request_run_id


def render_research_universe_builder(*, root: Path = Path("."), analyze_company=None) -> None:
    st.title("Research Launchpad")
    st.write("Tell me what you're interested in. I'll help build a Research Universe you can refine and analyze.")

    service = RCEBenchmarkExplorerService()
    known_identities = _known_identity_records(service)
    topics = established_topics(service)
    topic_by_name = {row.benchmark_name: row for row in topics}

    question = st.text_area(
        "What are you interested in researching?",
        key="universe_builder_question",
        height=130,
        placeholder="Describe an industry, technology, market segment, investment theme, or competitive landscape.",
    )
    st.caption("Examples: AI data-center networking · Robotics used in agriculture · Residential mortgage finance · Semiconductor memory companies")
    st.subheader("Companies you already know — optional")
    st.caption("Enter ticker symbols separated by commas.")
    raw_companies = st.text_area(
        "Ticker symbols",
        key="universe_builder_anchors",
        height=100,
        placeholder="CRWD, PANW, ZS",
        help="Enter ticker symbols separated by commas.",
        label_visibility="collapsed",
    )
    parsed_input = parse_ticker_input(raw_companies)
    if parsed_input.entries:
        st.caption("Starting companies: " + ", ".join(row.ticker for row in parsed_input.entries))
    if parsed_input.invalid_values:
        st.warning("Ticker symbols are required. Check: " + ", ".join(parsed_input.invalid_values))

    st.subheader("Browse established research topics — optional")
    selected_name = st.selectbox(
        "Established research topic",
        options=(None, *topic_by_name),
        format_func=lambda value: "Select a topic" if value is None else value,
        key="universe_builder_topic",
        label_visibility="collapsed",
    )

    saved_paths = _saved_options(root)
    st.subheader("Continue from saved research — optional")
    saved_path = st.selectbox(
        "Saved Research Universe",
        options=(None, *saved_paths),
        format_func=lambda value: "Select available research" if value is None else readable_universe_title(None, value.stem.replace("_", " ").title(), ""),
        key="universe_builder_saved",
        label_visibility="collapsed",
    ) if saved_paths else None
    if not saved_paths:
        st.caption("No saved Research Universes are available yet.")

    preview_id = "launch-preview"
    selected_topic = topic_by_name.get(selected_name)
    seeded = _topic_records(service, selected_topic.benchmark_id) if selected_topic else ()
    saved = _saved_records(saved_path, preview_id)
    manual = _manual_records(
        raw_companies, preview_id, known_records=(*seeded, *saved, *known_identities),
    )
    preview_universe = ResearchUniverseReviewService().assemble(
        universe_id=preview_id,
        title=readable_universe_title(selected_name, saved_path.stem if saved_path else None, question),
        research_question=question.strip(),
        starting_companies=(*seeded, *saved, *manual),
    )
    starting = preview_universe.approved_membership

    with st.container(border=True):
        st.subheader("Your research starting point")
        st.write(f"Research question: {question.strip() or 'Not entered'}")
        st.write(f"Established topic: {selected_name or 'Not selected'}")
        st.write(f"Known or starting companies: {len(starting)}")
        if starting:
            st.write(", ".join(row.ticker_or_identifier or row.company_name for row in starting))
        unresolved = tuple(row for row in starting if not row.ticker_or_identifier)
        if unresolved:
            st.caption("Identity not yet resolved: " + ", ".join(row.company_name for row in unresolved))
        sources = []
        if seeded:
            sources.append("established topic")
        if manual:
            sources.append("manual entry")
        if saved:
            sources.append("saved research")
        if saved_path:
            st.caption("Continuing from: " + readable_universe_title(None, saved_path.stem.replace("_", " ").title(), ""))

    meaningful = bool(question.strip() or selected_topic or manual or saved)
    if st.button("Launch Research", type="primary", disabled=not meaningful):
        universe_id = str(uuid4())
        base_starting = (
            (_topic_records(service, selected_topic.benchmark_id) if selected_topic else ())
            + _saved_records(saved_path, universe_id)
        )
        unresolved_manual = _manual_records(raw_companies, universe_id, known_records=base_starting)
        provider_error = None
        request_run_id = f"non-live:{universe_id}"
        if selected_topic:
            suggestions = _stored_suggestions(service, selected_topic.benchmark_id)
        else:
            try:
                suggestions, _generated_title, request_run_id = _provider_suggestions(
                    question, (*base_starting, *unresolved_manual), universe_id=universe_id,
                )
            except Exception as error:
                suggestions = ()
                provider_error = str(error)
        manual_records = _manual_records(
            raw_companies, universe_id,
            known_records=(*base_starting, *suggestions, *known_identities),
            use_market_data=True,
        )
        starting_records = (*base_starting, *manual_records)
        universe = ResearchUniverseReviewService().assemble(
            universe_id=universe_id,
            title=readable_universe_title(selected_name, saved_path.stem.replace("_", " ").title() if saved_path else None, question),
            research_question=question.strip() or (selected_topic.question if selected_topic else ""),
            starting_companies=starting_records,
            rce_suggestions=suggestions,
            established_topic=selected_name,
            provenance={
                "persistence": "session_only",
                "universe_type": UniverseType.SYSTEM_SEEDED if selected_topic else UniverseType.PRIVATE_USER,
                "established_topic_id": selected_topic.benchmark_id if selected_topic else None,
                "source_summary": ", ".join(sources) or "Question only",
                "original_question": question,
                "original_company_input": raw_companies,
                "saved_research_source": str(saved_path) if saved_path else None,
                "provider_error": provider_error,
                "request_run_id": request_run_id,
            },
        )
        st.session_state.current_research_universe = universe
        st.session_state.pop("active_universe_analysis_preflight", None)
        st.session_state.pop("active_universe_analysis_handoff", None)
        st.session_state.pop("active_universe_analysis_run", None)
        st.session_state.pop("active_universe_analysis_snapshot_id", None)
        st.session_state.pop("active_universe_analysis_snapshot_persistence_error", None)
        request_navigation("Research Universe")

    if not meaningful:
        st.caption("Enter a research question or choose at least one starting input to launch.")
