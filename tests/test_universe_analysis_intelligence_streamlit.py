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


def test_ready_presentation_renders_all_contract_sections_and_context():
    script = APP.replace(
        "page.render_universe_analysis()",
        '''
from tests.test_universe_analysis_change_detection import _pair
from src.universe_analysis_presentation_service import build_universe_analysis_presentation
baseline, current = _pair(field="technical_profile", before="Weak", after="Strong")
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
    assert headings[:9] == [
        "Universe Analysis", "Current Read", "What Deserves Attention", "What Changed",
        "Leaders", "Laggards", "Membership Changes", "Caveats", "Company comparison",
    ]
    assert any("Current snapshot:" in caption.value for caption in app.caption)
    assert any("Weak → Strong" in item.value for item in app.markdown)
