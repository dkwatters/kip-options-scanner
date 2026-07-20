import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from src.rce_benchmark_explorer_service import RCEBenchmarkExplorerService
from src.research_universe import (
    CandidateDisposition,
    IdentityStatus,
    ResearchUniverseReviewService,
    UniverseSource,
    UniverseState,
    normalized_matching_key,
    source_record,
)
from src.research_universe_review_page import (
    CURATOR_MODE,
    GENERAL_USER_MODE,
    curator_diagnostics_visible,
    promote_suggested_candidate,
    review_rows,
)
from src.research_universe_input import ResearchUniverseInputService


def record(name, ticker, source, **metadata):
    return source_record(
        {"company_name": name, "ticker": ticker, **metadata},
        source,
        source_reference=f"{source.value}:test",
    )


class ResearchUniverseTest(unittest.TestCase):
    def setUp(self):
        self.service = ResearchUniverseReviewService()

    def test_valid_promoted_ticker_resolves_equivalently_to_manual_entry(self):
        suggestion = record("Marvell Technology", "MRVL", UniverseSource.RCE_GENERATED)
        universe = self.assemble(rce=(suggestion,))
        promoted = promote_suggested_candidate(
            universe, "ticker:MRVL", ResearchUniverseInputService(),
        )
        _, manual_records = ResearchUniverseInputService().resolve(
            "MRVL", source_reference="manual:test", known_records=(suggestion,),
        )
        manual = self.service.assemble(
            universe_id="manual", title="Manual",
            starting_companies=manual_records,
        )
        assert promoted.approved_membership[0].identity_status == IdentityStatus.RESOLVED
        assert manual.approved_membership[0].identity_status == IdentityStatus.RESOLVED
        assert promoted.downstream_handoff().approved_constituents == ("MRVL",)

    def assemble(self, starting=(), rce=(), decisions=None, state=UniverseState.UNDER_REVIEW):
        return self.service.assemble(
            universe_id="universe-1",
            title="Test universe",
            research_question="Test a market",
            starting_companies=starting,
            rce_suggestions=rce,
            dispositions=decisions,
            state=state,
        )

    def test_curator_and_user_starting_sources_share_candidate_model_and_rules(self):
        rce = (record("Alpha", "AAA", UniverseSource.RCE_GENERATED),)
        curator = self.assemble(
            (record("Alpha", "AAA", UniverseSource.CURATOR_AUTHORED),), rce,
        )
        user = self.assemble(
            (record("Alpha", "AAA", UniverseSource.USER_ENTERED),), rce,
        )
        self.assertEqual(curator.candidates[0].normalized_matching_key, user.candidates[0].normalized_matching_key)
        self.assertEqual(curator.candidates[0].disposition, user.candidates[0].disposition)
        self.assertNotEqual(curator.candidates[0].source_records[0].source, user.candidates[0].source_records[0].source)

    def test_source_changes_provenance_not_one_sided_disposition(self):
        dispositions = {
            self.assemble((record("Alpha", "AAA", source),)).candidates[0].disposition
            for source in (
                UniverseSource.CURATOR_AUTHORED,
                UniverseSource.USER_ENTERED,
                UniverseSource.COMPANY_ANALYSIS_ANCHOR,
                UniverseSource.SAVED_UNIVERSE_REVISION,
                UniverseSource.IMPORTED,
            )
        }
        self.assertEqual(dispositions, {CandidateDisposition.INCLUDED})

    def test_matching_is_ticker_first(self):
        universe = self.assemble(
            (record("Old Name", "AAA", UniverseSource.USER_ENTERED),),
            (record("New Name", "AAA", UniverseSource.RCE_GENERATED),),
        )
        self.assertEqual(len(universe.candidates), 1)
        self.assertEqual(universe.candidates[0].normalized_matching_key, "ticker:AAA")
        self.assertEqual(universe.candidates[0].disposition, CandidateDisposition.INCLUDED)

    def test_name_fallback_matches_when_tickers_are_absent(self):
        universe = self.assemble(
            (record("Alpha Holdings", None, UniverseSource.USER_ENTERED),),
            (record("Alpha Holdings", None, UniverseSource.RCE_GENERATED),),
        )
        self.assertEqual(len(universe.candidates), 1)
        self.assertEqual(universe.candidates[0].normalized_matching_key, "name:alphaholdings")

    def test_agreements_are_automatically_included_for_every_origin(self):
        for source in UniverseSource:
            if source == UniverseSource.RCE_GENERATED:
                continue
            universe = self.assemble(
                (record("Alpha", "AAA", source),),
                (record("Alpha", "AAA", UniverseSource.RCE_GENERATED),),
            )
            self.assertEqual(universe.candidates[0].disposition, CandidateDisposition.INCLUDED)

    def test_explicit_removal_can_override_a_starting_company_without_deleting_evidence(self):
        key = normalized_matching_key("Alpha", "AAA")
        universe = self.assemble(
            (record("Alpha", "AAA", UniverseSource.USER_ENTERED),),
            (record("Alpha", "AAA", UniverseSource.RCE_GENERATED),),
            decisions={key: CandidateDisposition.REJECTED},
        )
        self.assertEqual(universe.candidates[0].disposition, CandidateDisposition.REJECTED)
        self.assertEqual(len(universe.candidates[0].source_records), 2)

    def test_starting_companies_are_included_and_rce_only_candidates_are_pending(self):
        universe = self.assemble(
            (record("Start", "STA", UniverseSource.USER_ENTERED),),
            (record("Suggestion", "SUG", UniverseSource.RCE_GENERATED),),
        )
        by_ticker = {row.ticker_or_identifier: row.disposition for row in universe.candidates}
        self.assertEqual(by_ticker["STA"], CandidateDisposition.INCLUDED)
        self.assertEqual(by_ticker["SUG"], CandidateDisposition.PENDING)

    def test_general_user_can_include_rce_only_suggestion(self):
        key = normalized_matching_key("Suggestion", "SUG")
        universe = self.assemble(
            rce=(record("Suggestion", "SUG", UniverseSource.RCE_GENERATED),),
            decisions={key: CandidateDisposition.INCLUDED},
        )
        self.assertEqual(universe.approved_membership[0].ticker_or_identifier, "SUG")

    def test_general_user_can_reject_rce_only_suggestion_without_deleting_history(self):
        key = normalized_matching_key("Suggestion", "SUG")
        universe = self.assemble(
            rce=(record("Suggestion", "SUG", UniverseSource.RCE_GENERATED),),
            decisions={key: CandidateDisposition.REJECTED},
        )
        self.assertEqual(len(universe.candidates), 1)
        self.assertEqual(universe.candidates[0].source_records[0].source, UniverseSource.RCE_GENERATED)
        self.assertEqual(universe.approved_membership, ())

    def test_pending_may_remain_when_universe_is_approved(self):
        universe = self.assemble(
            rce=(record("Suggestion", "SUG", UniverseSource.RCE_GENERATED),),
            state=UniverseState.APPROVED,
        )
        self.assertEqual(universe.state, UniverseState.APPROVED)
        self.assertEqual(universe.progress.pending, 1)

    def test_membership_is_agreements_plus_explicit_inclusions_only(self):
        key = normalized_matching_key("Explicit", "EXP")
        universe = self.assemble(
            starting=(
                record("Agreement", "AGR", UniverseSource.USER_ENTERED),
                record("Starting pending", "STA", UniverseSource.USER_ENTERED),
            ),
            rce=(
                record("Agreement renamed", "AGR", UniverseSource.RCE_GENERATED),
                record("Explicit", "EXP", UniverseSource.RCE_GENERATED),
                record("Pending", "PEN", UniverseSource.RCE_GENERATED),
                record("Rejected", "REJ", UniverseSource.RCE_GENERATED),
            ),
            decisions={
                key: CandidateDisposition.INCLUDED,
                normalized_matching_key("Rejected", "REJ"): CandidateDisposition.REJECTED,
            },
        )
        self.assertEqual(
            {row.ticker_or_identifier for row in universe.approved_membership},
            {"AGR", "STA", "EXP"},
        )

    def test_universe_type_does_not_change_disposition_rules(self):
        outcomes = set()
        for universe_type in ("private_user", "shared", "curated_official", "system_seeded", "imported"):
            universe = self.service.assemble(
                universe_id=universe_type,
                title="Type invariant",
                starting_companies=(record("Start", "STA", UniverseSource.USER_ENTERED),),
                rce_suggestions=(record("Suggestion", "SUG", UniverseSource.RCE_GENERATED),),
                provenance={"universe_type": universe_type},
            )
            outcomes.add(tuple((row.ticker_or_identifier, row.disposition) for row in universe.candidates))
        self.assertEqual(len(outcomes), 1)

    def test_revise_adds_manual_starting_company_immediately(self):
        universe = self.assemble(rce=(record("Suggestion", "SUG", UniverseSource.RCE_GENERATED),))
        revised = self.service.revise(
            universe,
            additional_starting_companies=(record("Manual", "MAN", UniverseSource.USER_ENTERED),),
        )
        self.assertIn("MAN", {row.ticker_or_identifier for row in revised.approved_membership})

    def test_manual_three_tickers_are_all_members_even_when_unresolved(self):
        records = tuple(
            source_record(
                {"company_name": ticker, "ticker": ticker, "supplied_value": ticker},
                UniverseSource.USER_ENTERED,
            )
            for ticker in ("CRWD", "PANW", "ZS")
        )
        universe = self.assemble(starting=records)
        self.assertEqual(
            {row.ticker_or_identifier for row in universe.approved_membership},
            {"CRWD", "PANW", "ZS"},
        )
        self.assertTrue(all(row.identity_status == IdentityStatus.UNRESOLVED for row in universe.approved_membership))

    def test_manual_ticker_promotes_matching_suggestion_and_preserves_provenance(self):
        universe = self.assemble(rce=(record("Zscaler, Inc.", "ZS", UniverseSource.RCE_GENERATED),))
        manual = source_record(
            {"company_name": "ZS", "ticker": "ZS", "supplied_value": "ZS"},
            UniverseSource.USER_ENTERED,
            source_reference="session:universe-1:manual-addition",
        )
        revised = self.service.revise(universe, additional_starting_companies=(manual,))
        self.assertEqual(len(revised.candidates), 1)
        member = revised.approved_membership[0]
        self.assertEqual((member.company_name, member.ticker_or_identifier), ("Zscaler, Inc.", "ZS"))
        self.assertEqual(member.identity_status, IdentityStatus.RESOLVED)
        self.assertEqual(member.inclusion_origin, "Explicit user entry")
        self.assertEqual({row.source for row in member.source_records}, {UniverseSource.USER_ENTERED, UniverseSource.RCE_GENERATED})
        self.assertEqual(revised.progress.pending, 0)

    def test_manual_canonical_name_promotes_suggestion_without_fuzzy_matching(self):
        universe = self.assemble(rce=(record("Zscaler, Inc.", "ZS", UniverseSource.RCE_GENERATED),))
        manual = source_record(
            {"company_name": "Zscaler", "supplied_value": "Zscaler"}, UniverseSource.USER_ENTERED,
        )
        revised = self.service.revise(universe, additional_starting_companies=(manual,))
        self.assertEqual(len(revised.approved_membership), 1)
        self.assertEqual(revised.approved_membership[0].ticker_or_identifier, "ZS")
        misspelled = source_record(
            {"company_name": "zscalar", "supplied_value": "zscalar"}, UniverseSource.USER_ENTERED,
        )
        separate = self.service.revise(universe, additional_starting_companies=(misspelled,))
        self.assertEqual(len(separate.candidates), 2)
        self.assertEqual(separate.approved_membership[0].identity_status, IdentityStatus.UNRESOLVED)

    def test_unresolved_manual_entry_is_preserved_but_not_silently_analyzed(self):
        manual = source_record(
            {"company_name": "Mystery Entry", "supplied_value": "Mystery Entry"}, UniverseSource.USER_ENTERED,
        )
        universe = self.assemble(starting=(manual,))
        member = universe.approved_membership[0]
        self.assertEqual(member.original_input, "Mystery Entry")
        self.assertEqual(member.identity_status, IdentityStatus.UNRESOLVED)
        handoff = universe.downstream_handoff()
        self.assertEqual(handoff.approved_constituents, ())
        self.assertEqual(handoff.total_member_count, 1)
        self.assertEqual(handoff.unresolved_members, ("Mystery Entry",))

    def test_duplicate_manual_add_is_idempotent_and_case_insensitive(self):
        universe = self.assemble()
        first = source_record({"company_name": "crwd", "ticker": "crwd", "supplied_value": "crwd"}, UniverseSource.USER_ENTERED)
        second = source_record({"company_name": "CRWD", "ticker": "CRWD", "supplied_value": "CRWD"}, UniverseSource.USER_ENTERED)
        revised = self.service.revise(universe, additional_starting_companies=(first, second))
        self.assertEqual(len(revised.approved_membership), 1)

    def test_manual_add_overrides_prior_rejection_as_explicit_membership(self):
        suggestion = record("Zscaler", "ZS", UniverseSource.RCE_GENERATED)
        key = normalized_matching_key("Zscaler", "ZS")
        universe = self.assemble(rce=(suggestion,), decisions={key: CandidateDisposition.REJECTED})
        manual = source_record({"company_name": "ZS", "ticker": "ZS", "supplied_value": "ZS"}, UniverseSource.USER_ENTERED)
        revised = self.service.revise(universe, additional_starting_companies=(manual,))
        self.assertEqual(revised.approved_membership[0].ticker_or_identifier, "ZS")

    def test_remove_members_preserves_source_history(self):
        universe = self.assemble((record("Manual", None, UniverseSource.USER_ENTERED),))
        key = universe.approved_membership[0].normalized_matching_key
        revised = self.service.remove_members(universe, (key,))
        self.assertEqual(revised.approved_membership, ())
        self.assertEqual(revised.candidates[0].disposition, CandidateDisposition.REJECTED)
        self.assertEqual(revised.candidates[0].source_records[0].company_name, "Manual")

    def test_downstream_handoff_is_exact_and_does_not_run_analysis(self):
        universe = self.assemble(
            (record("Alpha", "AAA", UniverseSource.USER_ENTERED),),
            (record("Alpha", "AAA", UniverseSource.RCE_GENERATED),),
        )
        handoff = universe.downstream_handoff()
        self.assertEqual(handoff.universe_id, "universe-1")
        self.assertEqual(handoff.universe_version, 1)
        self.assertEqual(handoff.approved_constituents, ("AAA",))
        self.assertEqual(handoff.expected_constituent_count, len(handoff.approved_constituents))

    def test_shared_review_rows_are_mode_independent(self):
        universe = self.assemble(
            (record("Alpha", "AAA", UniverseSource.USER_ENTERED),),
            (record("Alpha", "AAA", UniverseSource.RCE_GENERATED),),
        )
        rows = review_rows(universe)
        self.assertTrue(rows[0].starting_company)
        self.assertTrue(rows[0].rce_suggestion)
        self.assertFalse(curator_diagnostics_visible(GENERAL_USER_MODE))
        self.assertTrue(curator_diagnostics_visible(CURATOR_MODE))

    def test_existing_curator_approvals_are_readable_through_adapter(self):
        with tempfile.TemporaryDirectory() as directory:
            approval_path = Path(directory) / "approvals.json"
            explorer = RCEBenchmarkExplorerService(curator_approval_path=approval_path)
            explorer.approve_for_benchmark_of_record(
                "ai-data-center-networking-cabling", "ticker:CRDO",
            )
            comparison = explorer.corpus_comparison("ai-data-center-networking-cabling")
            universe = self.service.from_curator_comparison(
                comparison,
                explorer.approved_matching_keys(comparison.benchmark_id),
            )
            document = json.loads(approval_path.read_text(encoding="utf-8"))
        self.assertEqual(document["schema_version"], "curator-approvals-v0.1")
        self.assertIn("CRDO", {row.ticker_or_identifier for row in universe.approved_membership})
        self.assertEqual(universe.provenance["adapter"], "existing_curator_workflow")

    def test_curator_adapter_preserves_automatic_agreements(self):
        explorer = RCEBenchmarkExplorerService(curator_approval_path="missing-test-approvals.json")
        comparison = explorer.corpus_comparison("ai-data-center-networking-cabling")
        universe = self.service.from_curator_comparison(comparison)
        self.assertIn("ANET", {row.ticker_or_identifier for row in universe.approved_membership})
        self.assertFalse(Path("missing-test-approvals.json").exists())

    def test_source_records_are_immutable_audit_evidence(self):
        source = record("Alpha", "AAA", UniverseSource.IMPORTED, file_name="list.csv")
        universe = self.assemble((source,))
        with self.assertRaises(TypeError):
            universe.candidates[0].source_records[0].metadata["file_name"] = "changed.csv"


if __name__ == "__main__":
    unittest.main()
