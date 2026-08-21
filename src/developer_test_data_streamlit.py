"""Compact Streamlit controls for isolated deterministic demo scenarios."""
from __future__ import annotations

import streamlit as st

from src.developer_test_data import (
    DemoScenarioKind,
    create_demo_scenario,
    developer_tools_enabled,
    reset_demo_data,
)
from src.navigation import request_navigation
from src.universe_analysis_snapshot_repository import (
    universe_analysis_snapshot_repository_from_env,
)


_ACTIONS = (
    ("Create demo universe", DemoScenarioKind.FIRST_RUN),
    ("Generate first-run scenario", DemoScenarioKind.FIRST_RUN),
    ("Generate comparable change scenario", DemoScenarioKind.COMPARABLE_CHANGE),
    ("Generate no-change scenario", DemoScenarioKind.NO_CHANGE),
    ("Generate membership change scenario", DemoScenarioKind.MEMBERSHIP_CHANGE),
    ("Generate limited-comparability scenario", DemoScenarioKind.LIMITED_COMPARABILITY),
)


def render_developer_test_data_controls() -> None:
    if not developer_tools_enabled():
        return
    with st.expander("Developer tools", icon=":material/science:"):
        st.caption("Creates isolated deterministic demo snapshots. No providers or AI are called.")
        for label, kind in _ACTIONS:
            if st.button(label, key=f"developer_demo_{label.casefold().replace(' ', '_').replace('-', '_')}"):
                _create(kind)
        st.divider()
        confirmed = st.checkbox(
            "I understand reset removes only demo-prefixed snapshot records.",
            key="developer_demo_reset_confirmed",
        )
        if st.button(
            "Reset demo data", icon=":material/delete_sweep:",
            disabled=not confirmed, key="developer_demo_reset",
        ):
            try:
                with st.spinner("Removing demo data..."):
                    removed = reset_demo_data(universe_analysis_snapshot_repository_from_env())
                _clear_demo_session_state()
                st.success(f"Removed {removed} demo snapshot record(s). Non-demo data was untouched.")
            except Exception as error:
                st.error("Demo reset failed: " + str(error))


def _create(kind: DemoScenarioKind) -> None:
    try:
        with st.spinner("Generating deterministic demo scenario..."):
            result = create_demo_scenario(
                kind, universe_analysis_snapshot_repository_from_env(),
            )
        scenario = result.scenario
        st.session_state["current_research_universe"] = scenario.universe
        st.session_state["active_universe_analysis_handoff"] = scenario.handoff
        st.session_state["active_universe_analysis_run"] = scenario.current_run
        st.session_state["active_universe_analysis_snapshot_id"] = scenario.current_snapshot_id
        st.session_state["active_universe_analysis_demo_rows"] = scenario.current_rows
        st.session_state.pop("active_universe_analysis_snapshot_persistence_error", None)
        st.success(
            f"Created {scenario.universe_name} ({scenario.universe_id}); "
            f"{result.snapshots_created} new snapshot record(s)."
        )
        if st.button("Open Universe Analysis", key=f"open_demo_{kind.value}"):
            request_navigation("Universe Analysis")
    except Exception as error:
        st.error("Demo scenario generation failed: " + str(error))


def _clear_demo_session_state() -> None:
    handoff = st.session_state.get("active_universe_analysis_handoff")
    if str(getattr(handoff, "universe_id", "")).startswith("demo-"):
        for key in (
            "current_research_universe", "active_universe_analysis_handoff",
            "active_universe_analysis_run", "active_universe_analysis_snapshot_id",
            "active_universe_analysis_demo_rows", "universe_analysis_active_company",
        ):
            st.session_state.pop(key, None)
