from pathlib import Path


PAGE = Path("src/universe_analysis_page.py").read_text(encoding="utf-8")
CONTROLS = Path("src/developer_test_data_streamlit.py").read_text(encoding="utf-8")


def test_controls_are_gated_and_render_before_empty_analysis_state():
    assert "if not developer_tools_enabled():" in CONTROLS
    assert PAGE.index("render_developer_test_data_controls()") < PAGE.index(
        'handoff = st.session_state.get("active_universe_analysis_handoff")'
    )


def test_reset_requires_confirmation_and_is_demo_specific():
    assert "disabled=not confirmed" in CONTROLS
    assert "reset_demo_data" in CONTROLS
    assert "reset database" not in CONTROLS.casefold()


def test_demo_rows_are_used_only_for_demo_prefixed_runs():
    assert 'str(run.universe_id).startswith("demo-")' in PAGE
    assert "active_universe_analysis_demo_rows" in PAGE
