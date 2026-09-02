import os
import unittest
from unittest.mock import patch
from pathlib import Path

from streamlit.testing.v1 import AppTest


GENERAL_USER_APP = r'''
import streamlit as st
from src.research_universe import CandidateDisposition, ResearchUniverseReviewService, UniverseSource, UniverseState, normalized_matching_key, source_record
from src.research_universe_review_page import render_research_universe_review

def rec(name, ticker, source):
    return source_record({"company_name": name, "ticker": ticker, "identity_status": "resolved", "inclusion_rationale": f"Review {name}"}, source, source_reference=f"{source.value}:smoke")

starting = (
    rec("Agreement", "AGR", UniverseSource.USER_ENTERED),
    rec("Starting only", "STA", UniverseSource.USER_ENTERED),
)
rce = (
    rec("Agreement renamed", "AGR", UniverseSource.RCE_GENERATED),
    rec("Included suggestion", "INC", UniverseSource.RCE_GENERATED),
    rec("Rejected suggestion", "REJ", UniverseSource.RCE_GENERATED),
    rec("Pending suggestion", "PEN", UniverseSource.RCE_GENERATED),
)
decisions = {
    normalized_matching_key("Included suggestion", "INC"): CandidateDisposition.INCLUDED,
    normalized_matching_key("Rejected suggestion", "REJ"): CandidateDisposition.REJECTED,
}
universe = ResearchUniverseReviewService().assemble(
    universe_id="smoke-general", title="Smoke universe", research_question="Research the smoke market",
    starting_companies=starting, rce_suggestions=rce, dispositions=decisions,
    state=UniverseState.APPROVED,
)
render_research_universe_review(universe, key_prefix="smoke_general")
handoff = universe.downstream_handoff()
st.write(f"HANDOFF {handoff.universe_id} v{handoff.universe_version} {handoff.expected_constituent_count}")
'''


MUTATION_APP = r'''
import streamlit as st
from src.research_universe import CandidateDisposition, ResearchUniverseReviewService, UniverseSource, source_record
from src.research_universe_review_page import _suggestion_selection_key, render_research_universe_review

service = ResearchUniverseReviewService()
if "universe" not in st.session_state:
    suggestions = tuple(
        source_record(
            {"company_name": f"Company {index}", "ticker": f"C{index}"},
            UniverseSource.RCE_GENERATED,
        )
        for index in range(8)
    )
    st.session_state.universe = service.assemble(
        universe_id="mutation", title="Mutation test", rce_suggestions=suggestions,
    )

def set_disposition(key, disposition):
    st.session_state.universe = service.revise(
        st.session_state.universe, dispositions={key: disposition},
    )

pending = tuple(
    row for row in st.session_state.universe.candidates
    if row.in_rce_suggestions and row.disposition == CandidateDisposition.PENDING
)
if "selection_override" in st.session_state:
    st.session_state[_suggestion_selection_key("mutation", pending)] = {
        "selection": {"rows": st.session_state.pop("selection_override")}
    }

render_research_universe_review(
    st.session_state.universe,
    on_disposition=set_disposition,
    key_prefix="mutation",
)
'''


CURATOR_APP = r'''
import streamlit as st
from pathlib import Path
from src.rce_benchmark_explorer_service import RCEBenchmarkExplorerService
from src.research_universe import ResearchUniverseReviewService
from src.research_universe_review_page import CURATOR_MODE, render_research_universe_review

explorer = RCEBenchmarkExplorerService(curator_approval_path=Path("data/research/rce_benchmark_curator_approvals_v0.1.json"))
comparison = explorer.corpus_comparison("ai-data-center-networking-cabling")
universe = ResearchUniverseReviewService().from_curator_comparison(
    comparison, explorer.approved_matching_keys(comparison.benchmark_id),
)
render_research_universe_review(universe, mode=CURATOR_MODE, key_prefix="smoke_curator")
st.write(f"CURATOR {universe.universe_id} {universe.progress.included}")
'''


class ResearchUniverseStreamlitSmokeTest(unittest.TestCase):
    APP_TEST_TIMEOUT_SECONDS = 10

    def setUp(self):
        provider_environment = patch.dict(os.environ, {"RCE_PROVIDER": "mock"})
        provider_environment.start()
        self.addCleanup(provider_environment.stop)

    @staticmethod
    def _launchpad_app():
        return AppTest.from_string(r'''
from pathlib import Path
from src.research_universe_builder_page import render_research_universe_builder
render_research_universe_builder(root=Path("."))
''').run(timeout=ResearchUniverseStreamlitSmokeTest.APP_TEST_TIMEOUT_SECONDS)

    def test_launchpad_topics_empty_manual_input_and_live_preview(self):
        app = AppTest.from_string(r'''
from pathlib import Path
from src.research_universe_builder_page import render_research_universe_builder
render_research_universe_builder(root=Path("."))
''').run()
        self.assertFalse(app.exception)
        topic = next(row for row in app.selectbox if row.label == "Established research topic")
        self.assertEqual(len(topic.options), 18)  # prompt plus 17 established topics
        company_input = next(row for row in app.text_area if row.label == "Ticker symbols")
        self.assertEqual(company_input.value, "")
        self.assertNotIn("TSCO", company_input.value)
        self.assertEqual(company_input.placeholder, "CRWD, PANW, ZS")
        topic.select("AI Data-Center Networking and Cabling")
        company_input.set_value("MSFT")
        app.run()
        preview = "\n".join(row.value for row in app.markdown)
        self.assertIn("Established topic: AI Data-Center Networking and Cabling", preview)
        self.assertIn("Known or starting companies: 18", preview)
        self.assertIn("MSFT", preview)
        visible_copy = " ".join(
            [row.value for row in app.markdown]
            + [row.label for row in app.selectbox]
            + [row.label for row in app.text_area]
        ).casefold()
        self.assertNotIn("benchmark", visible_copy)
        self.assertNotIn("abm", visible_copy)

    def test_general_user_shared_review_renders_mixed_dispositions_and_exact_handoff(self):
        app = AppTest.from_string(GENERAL_USER_APP).run()
        self.assertFalse(app.exception)
        self.assertEqual(app.title[0].value, "Smoke universe")
        self.assertEqual([row.value for row in app.header], ["Universe Members"])
        self.assertEqual(
            [row.value for row in app.subheader],
            ["Summary", "Suggested Companies", "Add Companies"],
        )
        self.assertTrue(any(button.label == "Analyze Universe" for button in app.button))
        self.assertFalse(any(button.label == "Analyze Companies" for button in app.button))
        visible = " ".join([row.value for row in app.header] + [row.value for row in app.caption])
        self.assertNotIn("Population handoff contract", visible)
        self.assertNotIn("Included Companies", visible)
        current = app.dataframe[0].value
        self.assertEqual(set(current["Ticker or identifier"]), {"AGR", "STA", "INC"})
        self.assertTrue(any("HANDOFF smoke-general v1 3" in item.value for item in app.markdown))

    def test_question_only_empty_membership_explains_both_addition_paths(self):
        app = AppTest.from_string(r'''
from src.research_universe import ResearchUniverseReviewService
from src.research_universe_review_page import render_research_universe_review

universe = ResearchUniverseReviewService().assemble(
    universe_id="question-only",
    title="Nuclear Energy and Uranium",
    research_question="Which companies participate across the nuclear energy supply chain?",
)
render_research_universe_review(universe, key_prefix="question_only")
''').run()
        self.assertFalse(app.exception)
        self.assertEqual(app.title[0].value, "Nuclear Energy and Uranium")
        self.assertFalse(any("0 members" in row.value for row in app.caption))
        self.assertTrue(any("Ready for you to establish membership" in row.value for row in app.caption))
        self.assertEqual([row.value for row in app.subheader], ["Summary", "Suggested Companies", "Add Companies"])
        analyze = next(button for button in app.button if button.label == "Analyze Universe")
        self.assertTrue(analyze.disabled)

    def test_question_only_with_recommendations_is_a_normal_review_state(self):
        app = AppTest.from_string(r'''
from src.research_universe import ResearchUniverseReviewService, UniverseSource, source_record
from src.research_universe_review_page import render_research_universe_review

suggestions = (source_record({"company_name": "Cameco", "ticker": "CCJ"}, UniverseSource.RCE_GENERATED),)
universe = ResearchUniverseReviewService().assemble(
    universe_id="question-only", title="Nuclear Energy",
    research_question="Which companies participate across nuclear energy?",
    rce_suggestions=suggestions,
)
render_research_universe_review(universe, key_prefix="question_recommendations")
''').run()
        self.assertFalse(app.exception)
        self.assertTrue(any("We identified companies" in row.value for row in app.info))
        self.assertEqual(app.subheader[1].value, "Suggested Companies")
        self.assertTrue(next(button for button in app.button if button.label == "Analyze Universe").disabled)

    def test_visible_primary_workflow_has_no_implementation_terminology(self):
        launchpad = AppTest.from_string(r'''
from pathlib import Path
from src.research_universe_builder_page import render_research_universe_builder
render_research_universe_builder(root=Path("."))
''').run()
        universe = AppTest.from_string(GENERAL_USER_APP).run()
        visible = " ".join(
            [item.value for app in (launchpad, universe) for item in (*app.markdown, *app.caption, *app.info)]
            + [item.label for app in (launchpad, universe) for item in (*app.button, *app.selectbox, *app.text_area)]
        ).casefold()
        self.assertNotIn("benchmark", visible)
        self.assertNotIn("provider", visible)
        self.assertNotIn("population", visible)

    def test_launchpad_question_only_creates_recommendations_and_retains_question(self):
        app = self._launchpad_app()
        question = next(row for row in app.text_area if row.label == "What are you interested in researching?")
        question.set_value("Which companies support hyperscaler infrastructure?")
        app.run(timeout=self.APP_TEST_TIMEOUT_SECONDS)
        next(button for button in app.button if button.label == "Launch Research").click()
        app.run(timeout=self.APP_TEST_TIMEOUT_SECONDS)
        universe = app.session_state["current_research_universe"]
        self.assertEqual(universe.research_question, "Which companies support hyperscaler infrastructure?")
        self.assertGreater(universe.progress.pending, 0)
        self.assertEqual(universe.progress.included, 0)
        self.assertEqual(app.session_state["pending_selected_page"], "Research Universe")

    def test_launchpad_question_plus_companies_immediately_includes_companies(self):
        app = self._launchpad_app()
        next(row for row in app.text_area if row.label == "What are you interested in researching?").set_value(
            "Research cloud infrastructure."
        )
        next(row for row in app.text_area if row.label == "Ticker symbols").set_value("MSFT, AMZN")
        app.run(timeout=self.APP_TEST_TIMEOUT_SECONDS)
        next(button for button in app.button if button.label == "Launch Research").click()
        app.run(timeout=self.APP_TEST_TIMEOUT_SECONDS)
        universe = app.session_state["current_research_universe"]
        self.assertEqual(
            {row.ticker_or_identifier for row in universe.approved_membership},
            {"MSFT", "AMZN"},
        )

    def test_launchpad_established_topic_records_topic_and_membership(self):
        app = self._launchpad_app()
        next(row for row in app.selectbox if row.label == "Established research topic").select(
            "AI Data-Center Networking and Cabling"
        )
        app.run(timeout=self.APP_TEST_TIMEOUT_SECONDS)
        next(button for button in app.button if button.label == "Launch Research").click()
        app.run(timeout=self.APP_TEST_TIMEOUT_SECONDS)
        universe = app.session_state["current_research_universe"]
        self.assertEqual(universe.established_topic, "AI Data-Center Networking and Cabling")
        self.assertEqual(len(universe.approved_membership), 17)

    def test_analyze_universe_opens_exact_preflight_before_navigation(self):
        app = AppTest.from_string(r'''
import streamlit as st
from src.research_universe import ResearchUniverseReviewService, UniverseSource, source_record
from src.research_universe_review_page import render_current_research_universe_page

if "current_research_universe" not in st.session_state:
    st.session_state.current_research_universe = ResearchUniverseReviewService().assemble(
        universe_id="ready", title="Ready Universe", research_question="Research ready companies.",
        starting_companies=(source_record({"company_name": "Alpha", "ticker": "AAA", "identity_status": "resolved"}, UniverseSource.USER_ENTERED),),
    )
render_current_research_universe_page()
''').run(timeout=self.APP_TEST_TIMEOUT_SECONDS)
        next(button for button in app.button if button.label == "Analyze Universe").click()
        app.run(timeout=self.APP_TEST_TIMEOUT_SECONDS)
        preflight = app.session_state["active_universe_analysis_preflight"]
        self.assertEqual(preflight.handoff.approved_constituents, ("AAA",))
        self.assertEqual(preflight.handoff.total_member_count, 1)
        self.assertNotIn("pending_selected_page", app.session_state)

    def test_curator_mode_uses_same_renderer_and_retains_curator_context(self):
        app = AppTest.from_string(CURATOR_APP).run()
        self.assertFalse(app.exception)
        self.assertEqual(app.title[0].value, "ai-data-center-networking-cabling")
        self.assertTrue(any(
            "Curator mode" in item.value for item in app.caption
        ))
        self.assertTrue(any(
            "CURATOR ai-data-center-networking-cabling" in item.value
            for item in app.markdown
        ))

    def test_stale_selection_indexes_are_rejected_as_one_snapshot(self):
        from src.research_universe import ResearchUniverseReviewService, UniverseSource, source_record
        from src.research_universe_review_page import _selected_suggestions

        suggestions = ResearchUniverseReviewService().assemble(
            universe_id="selection", title="Selection",
            rce_suggestions=tuple(
                source_record({"company_name": name}, UniverseSource.RCE_GENERATED)
                for name in ("Alpha", "Beta", "Gamma")
            ),
        ).candidates
        self.assertEqual(
            [row.company_name for row in _selected_suggestions(suggestions, (0, 2))],
            ["Alpha", "Gamma"],
        )
        self.assertEqual(_selected_suggestions(suggestions, (0, 3)), ())
        self.assertEqual(_selected_suggestions(suggestions, (-1,)), ())

    def test_suggestion_widget_identity_changes_for_removal_and_reordering(self):
        app = AppTest.from_string(MUTATION_APP).run()
        suggestion_table = app.dataframe[0]
        original_key = suggestion_table.key
        self.assertEqual(len(suggestion_table.value), 8)

        app.session_state["selection_override"] = [0, 2, 5, 7]
        app.run()
        next(button for button in app.button if button.label == "Add Selected").click()
        app.run()

        self.assertFalse(app.exception)
        universe = app.session_state["universe"]
        self.assertEqual(
            {row.ticker_or_identifier for row in universe.approved_membership},
            {"C0", "C2", "C5", "C7"},
        )
        self.assertEqual(len(app.dataframe[1].value), 4)
        self.assertNotEqual(app.dataframe[1].key, original_key)
        self.assertTrue(next(
            button for button in app.button if button.label == "Add Selected"
        ).disabled)

        app.session_state["selection_override"] = [0, 2]
        app.run()
        next(button for button in app.button if button.label == "Reject").click()
        app.run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state["universe"].progress.pending, 2)

        app.session_state["selection_override"] = [1]
        app.run()
        next(button for button in app.button if button.label == "Add Selected").click()
        app.run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state["universe"].progress.pending, 1)

    def test_empty_and_single_remaining_suggestion_render_safely(self):
        app = AppTest.from_string(MUTATION_APP).run()
        original_key = app.dataframe[0].key
        app.session_state["selection_override"] = list(range(7))
        app.run()
        next(button for button in app.button if button.label == "Reject").click()
        app.run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.dataframe[0].value), 1)

        remaining_key = app.dataframe[0].key
        app.session_state["selection_override"] = [0]
        app.run()
        next(button for button in app.button if button.label == "Reject").click()
        app.run()
        self.assertFalse(app.exception)
        self.assertTrue(any(
            "There are no active suggestions" in row.value for row in app.caption
        ))

    def test_manual_add_promotes_suggestion_and_clears_scoped_input(self):
        app = AppTest.from_string(r'''
import streamlit as st
from src.research_universe import ResearchUniverseReviewService, UniverseSource, source_record
from src.research_universe_review_page import render_current_research_universe_page

if "current_research_universe" not in st.session_state:
    st.session_state.current_research_universe = ResearchUniverseReviewService().assemble(
        universe_id="promotion", title="Promotion",
        rce_suggestions=(source_record({"company_name": "Zscaler, Inc.", "ticker": "ZS"}, UniverseSource.RCE_GENERATED),),
    )
render_current_research_universe_page()
''').run()
        next(row for row in app.text_area if row.label == "Ticker symbols").set_value("ZS")
        app.run()
        next(button for button in app.button if button.label == "Add Companies").click()
        app.run()
        self.assertFalse(app.exception)
        universe = app.session_state["current_research_universe"]
        self.assertEqual(len(universe.approved_membership), 1)
        self.assertEqual(universe.progress.pending, 0)
        self.assertEqual(universe.approved_membership[0].company_name, "Zscaler, Inc.")
        self.assertEqual(next(row for row in app.text_area if row.label == "Ticker symbols").value, "")

    def test_unresolved_manual_member_is_visible_and_analysis_is_blocked(self):
        app = AppTest.from_string(r'''
import streamlit as st
from src.research_universe import ResearchUniverseReviewService
from src.research_universe_review_page import render_current_research_universe_page
if "current_research_universe" not in st.session_state:
    st.session_state.current_research_universe = ResearchUniverseReviewService().assemble(universe_id="unresolved", title="Unresolved")
render_current_research_universe_page()
''').run()
        next(row for row in app.text_area if row.label == "Ticker symbols").set_value("zscalar")
        app.run()
        next(button for button in app.button if button.label == "Add Companies").click()
        app.run()
        member_table = app.dataframe[0].value
        self.assertEqual(member_table.iloc[0]["Company"], "ZSCALAR")
        self.assertEqual(member_table.iloc[0]["Status"], "Identity unresolved")
        self.assertFalse(next(button for button in app.button if button.label == "Analyze Universe").disabled)
        next(button for button in app.button if button.label == "Analyze Universe").click()
        app.run()
        preflight = app.session_state["active_universe_analysis_preflight"]
        self.assertEqual(len(preflight.ledger), 1)
        self.assertEqual(preflight.ledger[0].status.value, "unresolved identity")
        self.assertTrue(next(button for button in app.button if button.label == "Continue with analyzable members").disabled)

    def test_start_new_research_clears_only_launchpad_draft_state(self):
        app = AppTest.from_string(r'''
import streamlit as st
from src.research_universe_builder_page import start_new_research
if not st.session_state.get("seeded"):
    st.session_state["universe_builder_question"] = "old question"
    st.session_state["universe_builder_anchors"] = "zscalar"
    st.session_state["universe_builder_topic"] = "old topic"
    st.session_state["current_research_universe"] = "preserved universe"
    st.session_state["seeded"] = True
st.session_state.setdefault("unrelated_navigation_state", "keep")
if st.button("Start new"):
    start_new_research()
''').run()
        next(button for button in app.button if button.label == "Start new").click()
        app.run()
        self.assertNotIn("universe_builder_question", app.session_state)
        self.assertNotIn("universe_builder_anchors", app.session_state)
        self.assertEqual(app.session_state["unrelated_navigation_state"], "keep")
        self.assertEqual(app.session_state["current_research_universe"], "preserved universe")
        self.assertEqual(app.session_state["pending_selected_page"], "Research Launchpad")

    def test_widget_keys_are_scoped_to_universe_identity(self):
        source = Path("src/research_universe_review_page.py").read_text(encoding="utf-8")
        self.assertIn('key_prefix=f"current_universe_{universe.universe_id}_v{universe.version}"', source)

    def test_suggestion_details_show_raw_validated_and_duplicate_identity(self):
        app = AppTest.from_string(r'''
import streamlit as st
from src.research_universe import ResearchUniverseReviewService, UniverseSource, source_record
from src.research_universe_review_page import _suggestion_selection_key, render_research_universe_review

universe = ResearchUniverseReviewService().assemble(
    universe_id="identity-details", title="Identity details",
    rce_suggestions=(source_record({
        "company_name": "Jabil Inc.",
        "ticker": "JBL",
        "raw_company_name": "Jabil Inc.",
        "raw_ticker_or_identifier": "JBLU",
        "identity_validation_status": "corrected",
        "candidate_identity_validation": {
            "validation_status": "corrected",
            "correction_applied": True,
            "correction_reason": "Authoritative correction.",
        },
        "duplicate_status": "not_in_seed_universe",
        "identity_status": "resolved",
    }, UniverseSource.RCE_GENERATED),),
)
pending = universe.candidates
if st.session_state.get("select_details"):
    st.session_state[_suggestion_selection_key("identity_details", pending)] = {
        "selection": {"rows": [0]}
    }
render_research_universe_review(universe, key_prefix="identity_details")
''').run()
        app.session_state["select_details"] = True
        app.run()
        captions = " ".join(row.value for row in app.caption)
        self.assertIn("Raw identity: Jabil Inc. / JBLU", captions)
        self.assertIn("Validated identity: Jabil Inc. / JBL", captions)
        self.assertIn("Duplicate status: Not in seed universe", captions)


if __name__ == "__main__":
    unittest.main()
