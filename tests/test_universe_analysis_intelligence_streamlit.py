from streamlit.testing.v1 import AppTest

from tests.test_universe_analysis_streamlit import APP


def test_presentation_assembly_failure_preserves_completed_analysis():
    script = APP.replace(
        "page.render_universe_analysis()",
        '''
st.session_state.active_universe_analysis_snapshot_id = "snapshot-current"
page.build_universe_analysis_presentation = lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("assembly unavailable"))
page.render_universe_analysis()
''',
    )
    app = AppTest.from_string(script).run()
    assert not app.exception
    assert any("intelligence presentation could not be assembled" in warning.value
               for warning in app.warning)
    assert any("Technical Profile" in frame.value.columns for frame in app.dataframe)


def test_no_persisted_snapshot_keeps_current_analysis_visible():
    app = AppTest.from_string(APP).run()
    assert not app.exception
    assert any("no persisted snapshot is selected" in warning.value for warning in app.warning)
    assert any("Technical Profile" in frame.value.columns for frame in app.dataframe)


def test_ready_presentation_consolidates_contract_sections_into_workspace():
    script = APP.replace(
        "page.render_universe_analysis()",
        '''
from tests.test_universe_analysis_change_detection import _pair
from dataclasses import replace
from src.universe_analysis_presentation_service import build_universe_analysis_presentation
baseline, current = _pair(field="technical_profile", before="Weak", after="Strong")
def rename(snapshot):
    return replace(snapshot, members=tuple(
        replace(member, ticker_or_identifier="CRWD", matching_key="ticker:CRWD", company_name="CrowdStrike")
        if member.ticker_or_identifier == "MIX" else member for member in snapshot.members
    ))
baseline, current = rename(baseline), rename(current)
class SnapshotRepo:
    def get(self, snapshot_id):
        return current if snapshot_id == current.snapshot_id else None
    def list_for_universe(self, universe_id, universe_version=None):
        return (current, baseline)
bundle = build_universe_analysis_presentation(current.snapshot_id, SnapshotRepo())
st.session_state.active_universe_analysis_snapshot_id = current.snapshot_id
page.build_universe_analysis_presentation = lambda *args, **kwargs: bundle
page.render_universe_analysis()
''',
    )
    app = AppTest.from_string(script).run()
    assert not app.exception
    headings = [item.value for item in app.subheader]
    assert headings[:3] == ["Universe Analysis", "Current Read", "Company comparison"]
    for redundant in ("What Deserves Attention", "What Changed", "Leaders", "Laggards",
                      "Membership Changes", "Caveats"):
        assert redundant not in headings
    assert any("Current snapshot:" in caption.value for caption in app.caption)
    comparison = next(frame.value for frame in app.dataframe if "Intelligence" in frame.value.columns)
    assert {"Intelligence", "Change", "Membership", "Status", "References"}.issubset(comparison.columns)
    assert any("Weak" in value and "Strong" in value for value in comparison["Change"].astype(str))
    assert any("Important caveats" in item.value for item in app.markdown)
    assert not any(button.label in {"View details", "View member details"} for button in app.button)
