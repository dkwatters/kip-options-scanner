import copy
import hashlib
import json
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest

from src.rce_benchmark_metrics import evaluate_benchmark, load_scoring_config
from src.rce_benchmark_repository import load_fixture
from src.rce_benchmark_run_repository import load_runs, list_unresolved_candidates, review_candidate
from src.rce_benchmark_runner import compare_run_sets, run_benchmark
from src.research_conversation import (
    MockResearchConversationProvider, ProviderMetadata, ResearchConversationResponse, utc_now,
)
from src.research_conversation.openai_provider import (
    LIVE_OPENAI_PROVIDER_VERIFICATION_MARKER,
)


FIXTURE_PATH = Path("tests/fixtures/rce_benchmarks/ai-data-center-networking-cabling.json")


def candidate(ticker, company, category, *, role=True, rationale=True, status="valid"):
    row = {
        "ticker": ticker, "company_name": company, "category": category,
        "entity_validation_status": status,
    }
    if role:
        row["role_summary"] = "Ecosystem role"
    if rationale:
        row["inclusion_rationale"] = "Relevant to the research question"
    return row


class RaisingProvider:
    provider_name = "openai"
    model_name = "test-model"

    def interpret(self, request):
        raise RuntimeError("provider unavailable")


class ResponseProvider:
    provider_name = "openai"
    model_name = "test-model"

    def __init__(self, response):
        self.response = response

    def interpret(self, request):
        return self.response


class RCEBenchmarkMetricsTests(unittest.TestCase):
    def setUp(self):
        self.fixture = load_fixture(FIXTURE_PATH)

    def artifact(self, rows):
        return {"candidate_securities": rows, "research_map": [], "warnings": []}

    def test_must_include_and_weighted_recall(self):
        result = evaluate_benchmark(self.fixture, self.artifact([
            candidate("AVGO", "Broadcom", "Networking silicon")
        ]))
        self.assertEqual(result.metrics["must_include_recall"], 0.5)
        self.assertAlmostEqual(result.metrics["weighted_candidate_recall"], 3 / 8)

    def test_must_exclude_penalty(self):
        fixture = copy.deepcopy(self.fixture)
        fixture["securities"].append({
            "ticker": "T", "company_name": "Carrier", "exchange": "NYSE",
            "listing_region": "US", "public_status": "public",
            "category_name": "General telecom carriers", "expectation": "must_exclude",
            "importance": 2, "role_summary": "Excluded", "evidence_summary": "Fixture",
            "notes": "",
        })
        result = evaluate_benchmark(fixture, self.artifact([candidate("T", "Carrier", "General telecom carriers")]))
        self.assertEqual(result.metrics["must_exclude_compliance"], 0.75)

    def test_category_coverage_and_excluded_category_penalty(self):
        result = evaluate_benchmark(self.fixture, self.artifact([
            candidate("AVGO", "Broadcom", "Networking silicon"),
            candidate("T", "Carrier", "General telecom carriers"),
        ]))
        self.assertAlmostEqual(result.metrics["category_coverage"], 0.25)

    def test_listing_constraints_flag_private_reference_as_investable(self):
        fixture = copy.deepcopy(self.fixture)
        fixture["securities"].append({
            "ticker": None, "company_name": "Private Co", "reference_identifier": "private:co",
            "exchange": None, "listing_region": "US", "public_status": "private",
            "category_name": "Networking silicon", "expectation": "private_reference",
            "importance": 1, "role_summary": "Context", "evidence_summary": "Fixture", "notes": "",
        })
        result = evaluate_benchmark(fixture, self.artifact([candidate(None, "Private Co", "Networking silicon")]))
        self.assertEqual(result.metrics["listing_constraint_compliance"], 0.75)

    def test_candidate_validity_and_rationale_completeness(self):
        result = evaluate_benchmark(self.fixture, self.artifact([
            candidate("AVGO", "Broadcom", "Networking silicon"),
            candidate("NEW", "Novel", "Optical and cabling", role=False, status="needs_review"),
        ]))
        self.assertEqual(result.metrics["candidate_validity"], 0.5)
        self.assertEqual(result.metrics["rationale_completeness"], 0.5)
        unexpected = next(row for row in result.candidate_results if row["ticker"] == "NEW")
        self.assertEqual(unexpected["comparison_outcome"], "unexpected_candidate")
        self.assertEqual(unexpected["reviewer_status"], "needs_verification")

    def test_rank_weighted_scoring_rewards_top_rank(self):
        top = evaluate_benchmark(self.fixture, self.artifact([
            candidate("AVGO", "Broadcom", "Networking silicon"),
            candidate("ANET", "Arista Networks", "Networking silicon"),
            candidate("COHR", "Coherent", "Optical and cabling"),
        ])).metrics["ranking_quality"]
        low = evaluate_benchmark(self.fixture, self.artifact([
            candidate("NEW", "Novel", "Networking silicon"),
            candidate("AVGO", "Broadcom", "Networking silicon"),
            candidate("ANET", "Arista Networks", "Networking silicon"),
            candidate("COHR", "Coherent", "Optical and cabling"),
        ])).metrics["ranking_quality"]
        self.assertGreater(top, low)

    def test_overall_score_configuration(self):
        config = load_scoring_config()
        self.assertAlmostEqual(sum(config["overall_weights"].values()), 1.0)
        result = evaluate_benchmark(self.fixture, self.artifact([]), config=config)
        expected = sum(result.metrics[name] * weight for name, weight in config["overall_weights"].items())
        self.assertAlmostEqual(result.overall_score, expected)
        self.assertNotIn("evidence_completeness", config["overall_weights"])


class RCEBenchmarkRunnerTests(unittest.TestCase):
    def setUp(self):
        self.fixture = load_fixture(FIXTURE_PATH)

    def test_failed_provider_call_is_a_failed_run(self):
        result = run_benchmark(self.fixture, RaisingProvider(), run_label="failed")
        self.assertEqual(result["run_status"], "failed")
        self.assertEqual(result["error_type"], "RuntimeError")

    def test_parser_schema_failure_is_recorded(self):
        now = utc_now()
        response = ResearchConversationResponse(
            metadata=ProviderMetadata("openai", "test-model", "test-prompt", now, now),
            structured_response={}, errors=["invalid JSON"],
        )
        result = run_benchmark(self.fixture, ResponseProvider(response), run_label="schema")
        self.assertEqual(result["run_status"], "failed")
        self.assertFalse(result["schema_valid"])

    def test_mock_fallback_is_rejected(self):
        now = utc_now()
        response = ResearchConversationResponse(
            metadata=ProviderMetadata(
                "mock", "mock-rce-v0.2", "test-prompt", now, now,
                selected_provider_name="openai", fallback_used=True, mock_provider_used=True,
            ),
            structured_response={
                "candidate_securities": [],
                "provider_verification_marker": LIVE_OPENAI_PROVIDER_VERIFICATION_MARKER,
            },
        )
        result = run_benchmark(self.fixture, ResponseProvider(response), run_label="fallback")
        self.assertEqual(result["run_status"], "failed")
        self.assertFalse(result["provider_verification_valid"])

    def test_benchmark_rejects_openai_response_without_verification_marker(self):
        now = utc_now()
        response = ResearchConversationResponse(
            metadata=ProviderMetadata("openai", "test-model", "test-prompt", now, now),
            structured_response={"candidate_securities": []},
        )

        result = run_benchmark(
            self.fixture, ResponseProvider(response), run_label="missing-marker"
        )

        self.assertEqual(result["run_status"], "failed")
        self.assertEqual(
            result["error_message"],
            "Provider verification marker is invalid or missing.",
        )
        self.assertFalse(result["provider_verification_valid"])

    def test_benchmark_accepts_exact_openai_verification_marker(self):
        now = utc_now()
        response = ResearchConversationResponse(
            metadata=ProviderMetadata("openai", "test-model", "test-prompt", now, now),
            structured_response={
                "candidate_securities": [],
                "provider_verification_marker": LIVE_OPENAI_PROVIDER_VERIFICATION_MARKER,
            },
        )

        result = run_benchmark(
            self.fixture, ResponseProvider(response), run_label="verified-marker"
        )

        self.assertEqual(result["run_status"], "success")
        self.assertTrue(result["provider_verification_valid"])

    def test_preview_creates_no_database_or_artifact_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database, artifacts = root / "run.sqlite", root / "artifacts"
            run_benchmark(
                self.fixture, MockResearchConversationProvider(), run_label="preview",
                persist=False, database_path=database, artifact_dir=artifacts,
            )
            self.assertFalse(database.exists())
            self.assertFalse(artifacts.exists())

    def test_persisted_run_stores_raw_and_parsed_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database, artifacts = root / "run.sqlite", root / "artifacts"
            result = run_benchmark(
                self.fixture, MockResearchConversationProvider(), run_label="persisted",
                persist=True, database_path=database, artifact_dir=artifacts,
            )
            self.assertTrue(Path(result["raw_response_path"]).exists())
            self.assertTrue(Path(result["parsed_artifact_path"]).exists())
            with closing(sqlite3.connect(database)) as connection:
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM rce_benchmark_run").fetchone()[0], 1)
                self.assertGreater(connection.execute("SELECT COUNT(*) FROM rce_benchmark_metric").fetchone()[0], 0)

    def test_persisted_run_reloads_scoring_provenance_and_stable_child_order(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = root / "run.sqlite"
            result = run_benchmark(
                self.fixture, MockResearchConversationProvider(), run_label="reloadable",
                persist=True, database_path=database, artifact_dir=root / "artifacts",
            )

            first = load_runs("reloadable", database)
            second = load_runs("reloadable", database)

            self.assertEqual(first, second)
            self.assertEqual(
                first[0]["scoring_config_version"],
                result["scoring_config"]["config_version"],
            )
            self.assertEqual(list(first[0]["metrics"]), sorted(first[0]["metrics"]))
            self.assertEqual(
                [row["category_name"] for row in first[0]["categories"]],
                sorted(row["category_name"] for row in first[0]["categories"]),
            )
            outcome_order = {
                "expected_returned": 0,
                "expected_missing": 1,
                "must_exclude_returned": 2,
                "unexpected_candidate": 3,
            }
            candidate_key = lambda row: (
                outcome_order.get(row["comparison_outcome"], 4),
                row["returned_rank"] is None,
                row["returned_rank"] if row["returned_rank"] is not None else 0,
                row["ticker"] or "",
                row["company_name"] or "",
                row["candidate_result_id"],
            )
            self.assertEqual(first[0]["candidates"], sorted(first[0]["candidates"], key=candidate_key))

            with closing(sqlite3.connect(database)) as connection:
                stored_config_version = connection.execute(
                    "SELECT scoring_config_version FROM rce_benchmark_run"
                ).fetchone()[0]
                metric_versions = {
                    row[0] for row in connection.execute(
                        "SELECT DISTINCT metric_version FROM rce_benchmark_metric"
                    )
                }
            self.assertEqual(stored_config_version, result["scoring_config"]["config_version"])
            self.assertEqual(metric_versions, {result["scoring_config"]["metric_version"]})

    def test_comparison_between_two_runs(self):
        old = [{
            "benchmark_id": "b", "metrics": {"weighted_candidate_recall": 0.0},
            "candidates": [{"ticker": "AVGO", "comparison_outcome": "expected_missing", "returned": 0, "validation_status": "not_returned"}],
            "categories": [], "latency_seconds": 2.0, "overall_score": 0.2,
        }]
        new = [{
            "benchmark_id": "b", "metrics": {"weighted_candidate_recall": 1.0},
            "candidates": [{"ticker": "AVGO", "comparison_outcome": "expected_returned", "returned": 1, "returned_rank": 1, "validation_status": "valid"}],
            "categories": [], "latency_seconds": 3.0, "overall_score": 0.8,
        }]
        comparison = compare_run_sets(old, new)["benchmarks"][0]
        self.assertEqual(comparison["newly_recovered_expected"], ["AVGO"])
        self.assertIn("overall score alone", comparison["interpretation"])

    def test_unexpected_candidate_review_preserves_fixture_and_audit(self):
        original = FIXTURE_PATH.read_bytes()
        original_hash = hashlib.sha256(original).hexdigest()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = run_benchmark(
                self.fixture, MockResearchConversationProvider(), run_label="review",
                persist=True, database_path=root / "run.sqlite", artifact_dir=root / "artifacts",
            )
            unresolved = list_unresolved_candidates(root / "run.sqlite")
            self.assertTrue(unresolved)
            review_candidate(
                unresolved[0]["candidate_result_id"], "valid_novel_discovery", "tester", "Relevant",
                database_path=root / "run.sqlite",
            )
            self.assertLess(len(list_unresolved_candidates(root / "run.sqlite")), len(unresolved))
            with closing(sqlite3.connect(root / "run.sqlite")) as connection:
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM rce_benchmark_review_audit").fetchone()[0], 1)
            self.assertEqual(hashlib.sha256(FIXTURE_PATH.read_bytes()).hexdigest(), original_hash)
            self.assertEqual(result["benchmark_id"], self.fixture["benchmark"]["benchmark_id"])


if __name__ == "__main__":
    unittest.main()
