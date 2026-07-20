import unittest
from pathlib import Path
from unittest.mock import patch

from src.navigation import apply_pending_navigation, request_navigation


class NavigationStateTest(unittest.TestCase):
    def test_pending_navigation_is_applied_and_cleared(self):
        state = {"selected_page": "Home", "pending_selected_page": "Research Launchpad"}
        with patch("src.navigation.st.session_state", state):
            applied = apply_pending_navigation()
        self.assertEqual(applied, "Research Launchpad")
        self.assertEqual(state["selected_page"], "Research Launchpad")
        self.assertNotIn("pending_selected_page", state)

    def test_navigation_request_only_sets_pending_widget_state(self):
        state = {"selected_page": "Home"}
        with (
            patch("src.navigation.st.session_state", state),
            patch("src.navigation.st.rerun") as rerun,
        ):
            request_navigation("Company Analysis")
        self.assertEqual(state["selected_page"], "Home")
        self.assertEqual(state["pending_selected_page"], "Company Analysis")
        rerun.assert_called_once_with()

    def test_app_applies_pending_navigation_before_sidebar_widget(self):
        source = Path("app.py").read_text(encoding="utf-8")
        main_source = source[source.index("def main():") :]
        self.assertLess(
            main_source.index("apply_pending_navigation()"),
            main_source.index('key="selected_page"'),
        )

    def test_home_and_company_handoffs_use_safe_navigation_helper(self):
        source = Path("app.py").read_text(encoding="utf-8")
        home_source = source[source.index("def render_home") : source.index("def actual_time_label")]
        self.assertIn("start_new_research()", home_source)
        self.assertIn('request_navigation("Company Analysis")', home_source)
        company_handoff = source[
            source.index("def launch_benchmark_company_analysis") : source.index("def enforce_app_password")
        ]
        self.assertIn('request_navigation("Company Analysis")', company_handoff)
        self.assertNotIn("selected_page", company_handoff)

    def test_launchpad_handoff_uses_safe_navigation_helper(self):
        source = Path("src/research_universe_builder_page.py").read_text(encoding="utf-8")
        self.assertIn('request_navigation("Research Universe")', source)
        self.assertNotIn("session_state.selected_page", source)
        self.assertNotIn('session_state["selected_page"]', source)

    def test_sidebar_navigation_and_home_route_remain_registered(self):
        source = Path("app.py").read_text(encoding="utf-8")
        self.assertIn('st.radio("Navigation", app_pages, key="selected_page")', source)
        self.assertIn('if selected_page == "Home":', source)
        self.assertIn('"Universe Analysis",', source)

    def test_home_has_two_primary_intents_and_user_facing_continue_research(self):
        source = Path("app.py").read_text(encoding="utf-8")
        home = source[source.index("def render_home") : source.index("def actual_time_label")]
        self.assertEqual(home.count('type="primary"'), 1)
        self.assertIn("What would you like to research?", home)
        self.assertIn("Start Research", home)
        self.assertIn("Analyze Company", home)
        self.assertIn("Continue Research", home)
        saved = source[source.index("def render_saved_research_universes") : source.index("def response_field")]
        self.assertNotIn('"Source": str(', saved)


if __name__ == "__main__":
    unittest.main()
