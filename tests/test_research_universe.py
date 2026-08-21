import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

from src.rce_benchmark_explorer_service import RCEBenchmarkExplorerService
from src.research_universe import (
    CandidateDisposition,
    IdentityStatus,
    ResearchUniverseReviewService,
    UniverseCandidate,
    UniverseSource,
    UniverseState,
    normalized_matching_key,
    source_record,
    trusted_promotion_reference,
    validate_candidate_partition_integrity,
)
from src.research_universe_review_page import (
    CURATOR_MODE,
    GENERAL_USER_MODE,
    curator_diagnostics_visible,
    promote_suggested_candidate,
    review_rows,
)
from src.research_universe_input import ResearchUniverseInputService
from src.research_universe_repository import SQLiteResearchUniverseRepository
from src.research_universe_analysis import (
    AnalysisMemberStatus, preflight_research_universe,
)


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
        rce = (record(
            "Alpha", "AAA", UniverseSource.RCE_GENERATED,
            identity_status=IdentityStatus.RESOLVED,
        ),)
        curator = self.assemble(
            (record(
                "Alpha", "AAA", UniverseSource.CURATOR_AUTHORED,
                identity_status=IdentityStatus.RESOLVED,
            ),), rce,
        )
        user = self.assemble(
            (record(
                "Alpha", "AAA", UniverseSource.USER_ENTERED,
                identity_status=IdentityStatus.RESOLVED,
            ),), rce,
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
            (record(
                "Old Name", "AAA", UniverseSource.USER_ENTERED,
                identity_status=IdentityStatus.RESOLVED,
            ),),
            (record(
                "New Name", "AAA", UniverseSource.RCE_GENERATED,
                identity_status=IdentityStatus.RESOLVED,
            ),),
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
                (record(
                    "Alpha", "AAA", source,
                    identity_status=IdentityStatus.RESOLVED,
                ),),
                (record(
                    "Alpha", "AAA", UniverseSource.RCE_GENERATED,
                    identity_status=IdentityStatus.RESOLVED,
                ),),
            )
            self.assertEqual(universe.candidates[0].disposition, CandidateDisposition.INCLUDED)

    def test_explicit_removal_can_override_a_starting_company_without_deleting_evidence(self):
        key = normalized_matching_key("Alpha", "AAA")
        universe = self.assemble(
            (record(
                "Alpha", "AAA", UniverseSource.USER_ENTERED,
                identity_status=IdentityStatus.RESOLVED,
            ),),
            (record(
                "Alpha", "AAA", UniverseSource.RCE_GENERATED,
                identity_status=IdentityStatus.RESOLVED,
            ),),
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
            {
                "company_name": "Zscaler, Inc.", "ticker": "ZS",
                "supplied_value": "ZS", "identity_status": IdentityStatus.RESOLVED,
            },
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

    def test_unresolved_manual_ticker_is_display_only_and_not_analyzable(self):
        manual = source_record(
            {
                "company_name": "Example Corp", "ticker": "EXMP",
                "supplied_value": "EXMP",
            },
            UniverseSource.USER_ENTERED, source_reference="manual:exmp",
        )
        universe = self.assemble(starting=(manual,))
        member = universe.approved_membership[0]

        self.assertTrue(
            member.normalized_matching_key.startswith("name:examplecorp:evidence:")
        )
        self.assertTrue(
            member.normalized_matching_key.removeprefix(
                "name:examplecorp:evidence:"
            )
        )
        self.assertEqual(member.ticker_or_identifier, "EXMP")
        self.assertEqual(member.identity_status, IdentityStatus.UNRESOLVED)
        preflight = preflight_research_universe(
            universe.downstream_handoff(), SimpleNamespace(get_price_history=lambda *a, **k: {})
        )
        self.assertEqual(preflight.analyzable_tickers, ())
        self.assertEqual(preflight.ledger[0].status, AnalysisMemberStatus.UNRESOLVED)

    def test_unresolved_ticker_does_not_grant_merge_authority(self):
        unresolved = source_record(
            {"company_name": "Example Corp", "ticker": "EXMP"},
            UniverseSource.USER_ENTERED, source_reference="manual:exmp",
        )
        validated = source_record(
            {
                "company_name": "Different Company", "ticker": "EXMP",
                "identity_status": IdentityStatus.RESOLVED,
            },
            UniverseSource.RCE_GENERATED, source_reference="rce:exmp",
        )
        universe = self.assemble(starting=(unresolved,), rce=(validated,))

        unresolved_key = next(
            row.normalized_matching_key for row in universe.candidates
            if row.normalized_matching_key.startswith("name:examplecorp:evidence:")
        )
        self.assertEqual(
            {row.normalized_matching_key for row in universe.candidates},
            {unresolved_key, "ticker:EXMP"},
        )
        self.assertEqual(
            next(row for row in universe.candidates
                 if row.normalized_matching_key == unresolved_key).identity_status,
            IdentityStatus.UNRESOLVED,
        )

    def test_conflicting_unresolved_raw_tickers_have_no_arbitrary_display_ticker(self):
        first = source_record(
            {
                "company_name": "Example Corp", "ticker": "OLD1",
                "identity_status": IdentityStatus.UNRESOLVED,
            },
            UniverseSource.USER_ENTERED, source_reference="manual:old1",
        )
        second = source_record(
            {
                "company_name": "Example Corporation", "ticker": "OLD2",
                "identity_status": IdentityStatus.UNRESOLVED,
            },
            UniverseSource.RCE_GENERATED, source_reference="rce:old2",
        )
        universe = self.assemble(starting=(first,), rce=(second,))

        self.assertEqual(len(universe.candidates), 2)
        self.assertTrue(all(
            member.normalized_matching_key.startswith("name:")
            for member in universe.candidates
        ))
        self.assertEqual(
            {member.ticker_or_identifier for member in universe.candidates},
            {"OLD1", "OLD2"},
        )
        self.assertTrue(all(
            len(member.source_records) == 1 for member in universe.candidates
        ))

    def test_validated_ticker_has_canonical_and_display_precedence(self):
        validated = source_record(
            {
                "company_name": "Example Corp", "ticker": "EXMP",
                "identity_status": IdentityStatus.RESOLVED,
            },
            UniverseSource.RCE_GENERATED, source_reference="rce:validated-exmp",
        )
        manual_name = source_record(
            {"company_name": "Example", "supplied_value": "Example"},
            UniverseSource.USER_ENTERED, source_reference="manual:example",
        )
        universe = self.assemble(starting=(manual_name,), rce=(validated,))
        member = universe.candidates[0]

        self.assertEqual(member.normalized_matching_key, "ticker:EXMP")
        self.assertEqual(member.ticker_or_identifier, "EXMP")
        self.assertEqual(member.identity_status, IdentityStatus.RESOLVED)

    def test_validated_display_ticker_preserves_provider_punctuation(self):
        validated = source_record(
            {
                "company_name": "Unsupported Symbol", "ticker": "ZS-AI",
                "identity_status": IdentityStatus.RESOLVED,
            },
            UniverseSource.USER_ENTERED, source_reference="manual:zs-ai",
        )
        universe = self.assemble(starting=(validated,))
        member = universe.candidates[0]

        self.assertEqual(member.normalized_matching_key, "ticker:ZSAI")
        self.assertEqual(member.ticker_or_identifier, "ZS-AI")
        preflight = preflight_research_universe(
            universe.downstream_handoff(),
            SimpleNamespace(get_price_history=lambda *a, **k: self.fail(
                "Unsupported provider-facing symbol must not be requested."
            )),
        )
        self.assertEqual(preflight.analyzable_tickers, ())
        self.assertEqual(preflight.ledger[0].status, AnalysisMemberStatus.UNSUPPORTED)

    def test_stable_security_id_absorbs_uniquely_mapped_ticker_only_evidence(self):
        security = source_record({
            "company_name": "Alpha", "ticker": "AAA", "identity_status": "resolved",
            "validated_security_id": "SEC1",
        }, UniverseSource.RCE_GENERATED, source_reference="rce:sec1")
        ticker_only = source_record({
            "company_name": "Alpha Inc.", "ticker": "AAA", "identity_status": "resolved",
        }, UniverseSource.USER_ENTERED, source_reference="manual:aaa")

        signatures = []
        for records in ((security, ticker_only), (ticker_only, security)):
            universe = self.service.assemble(
                universe_id="stable-id", title="Stable ID",
                starting_companies=tuple(
                    row for row in records if row.source != UniverseSource.RCE_GENERATED
                ),
                rce_suggestions=tuple(
                    row for row in records if row.source == UniverseSource.RCE_GENERATED
                ),
            )
            signatures.append(self._canonical_signature(universe))
            self.assertEqual(len(universe.candidates), 1)
            self.assertEqual(
                universe.candidates[0].normalized_matching_key, "security:SEC1"
            )
            self.assertEqual(len(universe.candidates[0].source_records), 2)
        self.assertEqual(signatures[0], signatures[1])

    def test_competing_security_ids_do_not_absorb_ticker_only_evidence(self):
        records = (
            source_record({
                "company_name": "Alpha A", "ticker": "AAA",
                "identity_status": "resolved", "validated_security_id": "SEC1",
            }, UniverseSource.RCE_GENERATED, source_reference="rce:sec1"),
            source_record({
                "company_name": "Alpha B", "ticker": "AAA",
                "identity_status": "resolved", "validated_security_id": "SEC2",
            }, UniverseSource.RCE_GENERATED, source_reference="rce:sec2"),
            source_record({
                "company_name": "Alpha Unknown", "ticker": "AAA",
                "identity_status": "resolved",
            }, UniverseSource.USER_ENTERED, source_reference="manual:aaa"),
        )
        universe = self.service.assemble(
            universe_id="competing-security", title="Competing security",
            starting_companies=(records[2],), rce_suggestions=records[:2],
        )

        self.assertEqual(
            {row.normalized_matching_key for row in universe.candidates},
            {"security:SEC1", "security:SEC2", "ticker:AAA"},
        )
        self.assertTrue(all(
            row.identity_status == IdentityStatus.AMBIGUOUS
            for row in universe.candidates
        ))
        self.assertEqual(
            sum(len(row.source_records) for row in universe.candidates), 3
        )

    def test_one_security_with_conflicting_current_tickers_is_deterministic(self):
        first = source_record({
            "company_name": "Alpha", "ticker": "AAA", "identity_status": "resolved",
            "validated_security_id": "SEC1",
        }, UniverseSource.RCE_GENERATED, source_reference="rce:aaa")
        second = source_record({
            "company_name": "Alpha Inc.", "ticker": "AAB", "identity_status": "resolved",
            "validated_security_id": "SEC1",
        }, UniverseSource.RCE_GENERATED, source_reference="rce:aab")
        results = []
        for records in ((first, second), (second, first)):
            universe = self.service.assemble(
                universe_id="ticker-conflict", title="Ticker conflict",
                rce_suggestions=records,
            )
            candidate = universe.candidates[0]
            results.append(self._canonical_signature(universe))
            self.assertEqual(candidate.normalized_matching_key, "security:SEC1")
            self.assertEqual(candidate.identity_status, IdentityStatus.AMBIGUOUS)
            self.assertIsNone(candidate.ticker_or_identifier)
        self.assertEqual(results[0], results[1])

    def test_trusted_promotion_requires_exact_unique_original_source(self):
        original = source_record({
            "company_name": "Zscaler", "ticker": "ZS",
            "identity_status": "unresolved",
            "candidate_identity": "candidate:zscaler",
        }, UniverseSource.RCE_GENERATED, source_reference="rce:zscaler")
        promoted_base = source_record({
            "company_name": "Zscaler Inc.", "ticker": "ZS",
            "identity_status": "resolved", "identity_validation_status": "valid",
        }, UniverseSource.USER_ENTERED,
            source_reference="session:trusted:suggestion-promotion")
        link = trusted_promotion_reference(
            original, promoted_base, candidate_identity="candidate:zscaler",
            validation_result="valid",
        )
        promoted = replace(
            promoted_base,
            metadata={**dict(promoted_base.metadata), "trusted_promotion_reference": link},
        )
        universe = self.service.assemble(
            universe_id="trusted", title="Trusted",
            starting_companies=(promoted,), rce_suggestions=(original,),
        )
        self.assertEqual(len(universe.candidates), 1)
        self.assertEqual(universe.candidates[0].normalized_matching_key, "ticker:ZS")
        self.assertEqual(len(universe.candidates[0].source_records), 2)
        with tempfile.TemporaryDirectory() as directory:
            repository = SQLiteResearchUniverseRepository(
                Path(directory) / "trusted.sqlite"
            )
            repository.save(universe)
            restored = repository.get(universe.universe_id)
        original_link = next(
            record.metadata["trusted_promotion_reference"]
            for record in universe.candidates[0].source_records
            if "trusted_promotion_reference" in record.metadata
        )
        restored_link = next(
            record.metadata["trusted_promotion_reference"]
            for record in restored.candidates[0].source_records
            if "trusted_promotion_reference" in record.metadata
        )
        self.assertEqual(restored_link, original_link)
        self.assertEqual(
            self._canonical_signature(self.service.revise(restored)),
            self._canonical_signature(restored),
        )

        mismatched = replace(
            promoted,
            metadata={
                **dict(promoted.metadata),
                "trusted_promotion_reference": {
                    **link, "original_source_reference": "rce:other",
                },
            },
        )
        with self.assertRaisesRegex(
            ValueError, "Promotion state lacks trusted exact-source evidence"
        ):
            self.service.assemble(
                universe_id="mismatch", title="Mismatch",
                starting_companies=(mismatched,), rce_suggestions=(original,),
            )

    def test_trusted_promotion_rejects_duplicate_identity_and_raw_conflict(self):
        original = source_record({
            "company_name": "Zscaler", "ticker": "ZS",
            "identity_status": "unresolved", "candidate_identity": "candidate:same",
        }, UniverseSource.RCE_GENERATED, source_reference="rce:zscaler")
        duplicate = source_record({
            "company_name": "Unrelated", "ticker": "BAD",
            "identity_status": "unresolved", "candidate_identity": "candidate:same",
        }, UniverseSource.RCE_GENERATED, source_reference="rce:unrelated")
        promoted_base = source_record({
            "company_name": "Zscaler Inc.", "ticker": "ZS",
            "identity_status": "resolved", "identity_validation_status": "valid",
        }, UniverseSource.USER_ENTERED,
            source_reference="session:trusted:suggestion-promotion")
        promoted = replace(promoted_base, metadata={
            **dict(promoted_base.metadata),
            "trusted_promotion_reference": trusted_promotion_reference(
                original, promoted_base, candidate_identity="candidate:same",
                validation_result="valid",
            ),
        })
        with self.assertRaisesRegex(
            ValueError, "Promotion state lacks trusted exact-source evidence"
        ):
            self.service.assemble(
                universe_id="duplicate-link", title="Duplicate link",
                starting_companies=(promoted,),
                rce_suggestions=(original, duplicate),
            )

        conflicting_link = dict(promoted.metadata["trusted_promotion_reference"])
        conflicting_link["expected_raw_ticker"] = "BAD"
        conflicting = replace(promoted, metadata={
            **dict(promoted.metadata),
            "trusted_promotion_reference": conflicting_link,
        })
        with self.assertRaisesRegex(
            ValueError, "Promotion state lacks trusted exact-source evidence"
        ):
            self.service.assemble(
                universe_id="raw-conflict", title="Raw conflict",
                starting_companies=(conflicting,), rce_suggestions=(original,),
            )

    def test_trusted_correction_result_must_match_promoted_validation_status(self):
        original = source_record({
            "company_name": "Victim Co", "ticker": "BAD",
            "identity_status": "unresolved", "candidate_identity": "candidate:victim",
        }, UniverseSource.RCE_GENERATED, source_reference="rce:victim")
        promoted_base = source_record({
            "company_name": "Zscaler Inc.", "ticker": "ZS",
            "identity_status": "resolved", "identity_validation_status": "valid",
        }, UniverseSource.USER_ENTERED,
            source_reference="session:status-mismatch:suggestion-promotion")
        promoted = replace(promoted_base, metadata={
            **dict(promoted_base.metadata),
            "trusted_promotion_reference": trusted_promotion_reference(
                original, promoted_base, candidate_identity="candidate:victim",
                validation_result="corrected",
            ),
        })

        with self.assertRaisesRegex(
            ValueError, "Promotion state lacks trusted exact-source evidence"
        ):
            self.service.assemble(
                universe_id="status-mismatch", title="Status mismatch",
                starting_companies=(promoted,), rce_suggestions=(original,),
            )

    def test_corrected_promotion_requires_complete_authoritative_provenance(self):
        complete_validation = {
            "schema_version": "candidate-identity-validation-result-v0.1",
            "candidate_id": "candidate:jabil",
            "raw_company_name": "Jabil Inc.",
            "raw_ticker_or_identifier": "JBLU",
            "normalized_company_name": "Jabil Inc.",
            "normalized_ticker_or_identifier": "JBL",
            "validation_status": "corrected",
            "correction_applied": True,
            "correction_reason": "Authoritative ticker correction.",
            "authoritative_source": "provider-free fixture",
            "source_reference": "fixture://security/JBL",
            "resolution_source": "authoritative_evidence",
        }

        for field in (
            "authoritative_source", "source_reference", "correction_reason",
            "schema_version",
        ):
            invalid_validation = dict(complete_validation)
            invalid_validation[field] = None
            if field == "correction_reason":
                invalid_validation["resolution_source"] = None
            original = source_record({
                "company_name": "Jabil Inc.", "ticker": "JBL",
                "raw_ticker_or_identifier": "JBLU",
                "identity_status": "resolved",
                "candidate_identity": "candidate:jabil",
                "candidate_identity_validation": invalid_validation,
            }, UniverseSource.RCE_GENERATED, source_reference="rce:jabil")
            promoted_base = source_record({
                "company_name": "Jabil Inc.", "ticker": "JBL",
                "identity_status": "resolved",
                "identity_validation_status": "corrected",
                "candidate_identity": "candidate:jabil",
                "candidate_identity_validation": invalid_validation,
            }, UniverseSource.USER_ENTERED,
                source_reference="session:jabil:suggestion-promotion")
            promoted = replace(promoted_base, metadata={
                **dict(promoted_base.metadata),
                "trusted_promotion_reference": trusted_promotion_reference(
                    original, promoted_base,
                    candidate_identity="candidate:jabil",
                    validation_result="corrected",
                ),
            })

            with self.subTest(missing=field), self.assertRaisesRegex(
                ValueError, "Promotion state lacks trusted exact-source evidence"
            ):
                self.service.assemble(
                    universe_id=f"invalid-{field}", title="Invalid correction",
                    starting_companies=(promoted,), rce_suggestions=(original,),
                )

        original = source_record({
            "company_name": "Jabil Inc.", "ticker": "JBL",
            "raw_ticker_or_identifier": "JBLU",
            "identity_status": "resolved",
            "candidate_identity": "candidate:jabil",
            "candidate_identity_validation": complete_validation,
        }, UniverseSource.RCE_GENERATED, source_reference="rce:jabil-valid")
        promoted_base = source_record({
            "company_name": "Jabil Inc.", "ticker": "JBL",
            "identity_status": "resolved",
            "identity_validation_status": "corrected",
            "candidate_identity": "candidate:jabil",
            "candidate_identity_validation": complete_validation,
        }, UniverseSource.USER_ENTERED,
            source_reference="session:jabil-valid:suggestion-promotion")
        promoted = replace(promoted_base, metadata={
            **dict(promoted_base.metadata),
            "trusted_promotion_reference": trusted_promotion_reference(
                original, promoted_base, candidate_identity="candidate:jabil",
                validation_result="corrected",
            ),
        })
        valid = self.service.assemble(
            universe_id="valid-correction", title="Valid correction",
            starting_companies=(promoted,), rce_suggestions=(original,),
        )
        unsupported_validation = {
            **complete_validation, "authoritative_source": None,
        }
        corrupted_records = tuple(
            replace(record, metadata={
                **dict(record.metadata),
                "candidate_identity_validation": unsupported_validation,
            })
            for record in valid.candidates[0].source_records
        )
        corrupted_candidate = replace(
            valid.candidates[0], source_records=corrupted_records,
        )
        object.__setattr__(valid, "candidates", (corrupted_candidate,))
        with tempfile.TemporaryDirectory() as directory:
            repository = SQLiteResearchUniverseRepository(
                Path(directory) / "bad-correction.sqlite"
            )
            with self.assertRaisesRegex(
                ValueError, "Promotion state lacks trusted exact-source evidence"
            ):
                repository.save(valid)

    def test_corrected_promotion_binds_nested_validation_to_target_identity(self):
        complete_validation = {
            "schema_version": "candidate-identity-validation-result-v0.1",
            "candidate_id": "candidate:jabil",
            "raw_company_name": "Jabil Inc.",
            "raw_ticker_or_identifier": "JBLU",
            "normalized_company_name": "Jabil Inc.",
            "normalized_ticker_or_identifier": "JBL",
            "validation_status": "corrected",
            "correction_applied": True,
            "correction_reason": "Authoritative ticker correction.",
            "authoritative_source": "provider-free fixture",
            "source_reference": "fixture://security/JBL",
            "resolution_source": "authoritative_evidence",
        }

        def records(validation, *, promoted_candidate_identity="candidate:jabil"):
            original = source_record({
                "company_name": "Jabil Inc.", "ticker": "JBL",
                "raw_ticker_or_identifier": "JBLU",
                "identity_status": "resolved",
                "candidate_identity": "candidate:jabil",
                "candidate_identity_validation": validation,
            }, UniverseSource.RCE_GENERATED, source_reference="rce:jabil-binding")
            promoted_base = source_record({
                "company_name": "Jabil Inc.", "ticker": "JBL",
                "identity_status": "resolved",
                "identity_validation_status": "corrected",
                "candidate_identity": promoted_candidate_identity,
                "candidate_identity_validation": validation,
            }, UniverseSource.USER_ENTERED,
                source_reference="session:jabil-binding:suggestion-promotion")
            promoted = replace(promoted_base, metadata={
                **dict(promoted_base.metadata),
                "trusted_promotion_reference": trusted_promotion_reference(
                    original, promoted_base,
                    candidate_identity="candidate:jabil",
                    validation_result="corrected",
                ),
            })
            return original, promoted

        invalid_values = (
            ("candidate_id", "candidate:other"),
            ("candidate_id", None),
            ("raw_ticker_or_identifier", "EVIL"),
            ("raw_ticker_or_identifier", "JBLU,EVIL"),
            ("raw_ticker_or_identifier", None),
            ("raw_company_name", "Unrelated Company"),
            ("raw_company_name", " "),
        )
        for field, value in invalid_values:
            invalid_validation = {**complete_validation, field: value}
            original, promoted = records(invalid_validation)
            before = (
                dict(original.metadata["candidate_identity_validation"]),
                dict(promoted.metadata["candidate_identity_validation"]),
            )
            with self.subTest(field=field, value=value), self.assertRaisesRegex(
                ValueError, "Promotion state lacks trusted exact-source evidence"
            ):
                self.service.assemble(
                    universe_id=f"invalid-binding-{field}-{value}",
                    title="Invalid binding",
                    starting_companies=(promoted,),
                    rce_suggestions=(original,),
                )
            self.assertEqual(
                (
                    dict(original.metadata["candidate_identity_validation"]),
                    dict(promoted.metadata["candidate_identity_validation"]),
                ),
                before,
            )

        copied_validation = {
            **complete_validation,
            "candidate_id": "candidate:copied",
            "raw_company_name": "Copied Company",
            "raw_ticker_or_identifier": "COPY",
        }
        original, promoted = records(copied_validation)
        with self.assertRaisesRegex(
            ValueError, "Promotion state lacks trusted exact-source evidence"
        ):
            self.service.assemble(
                universe_id="copied-validation", title="Copied validation",
                starting_companies=(promoted,), rce_suggestions=(original,),
            )

        for promoted_identity in (None, " ", "candidate:other"):
            original, promoted = records(
                complete_validation,
                promoted_candidate_identity=promoted_identity,
            )
            before = (
                dict(original.metadata),
                dict(promoted.metadata),
            )
            with self.subTest(
                promoted_candidate_identity=promoted_identity
            ), self.assertRaisesRegex(
                ValueError, "Promotion state lacks trusted exact-source evidence"
            ):
                self.service.assemble(
                    universe_id=f"invalid-promoted-identity-{promoted_identity}",
                    title="Invalid promoted identity",
                    starting_companies=(promoted,),
                    rce_suggestions=(original,),
                )
            self.assertEqual((dict(original.metadata), dict(promoted.metadata)), before)

        original, promoted = records(complete_validation)
        valid = self.service.assemble(
            universe_id="valid-binding", title="Valid binding",
            starting_companies=(promoted,), rce_suggestions=(original,),
        )
        for field, value in (
            ("candidate_id", "candidate:other"),
            ("raw_ticker_or_identifier", "EVIL"),
            ("raw_company_name", "Unrelated Company"),
        ):
            invalid_validation = {**complete_validation, field: value}
            corrupted_records = tuple(
                replace(record, metadata={
                    **dict(record.metadata),
                    "candidate_identity_validation": invalid_validation,
                })
                for record in valid.candidates[0].source_records
            )
            corrupted_candidate = replace(
                valid.candidates[0], source_records=corrupted_records,
            )
            corrupted = replace(valid, candidates=valid.candidates)
            object.__setattr__(corrupted, "candidates", (corrupted_candidate,))
            with tempfile.TemporaryDirectory() as directory:
                repository = SQLiteResearchUniverseRepository(
                    Path(directory) / f"bad-{field}.sqlite"
                )
                with self.subTest(repository_field=field), self.assertRaisesRegex(
                    ValueError, "Promotion state lacks trusted exact-source evidence"
                ):
                    repository.save(corrupted)

        original, promoted = records(
            complete_validation,
            promoted_candidate_identity="candidate:other",
        )
        corrupted_candidate = replace(
            valid.candidates[0],
            source_records=(promoted, original),
        )
        before = tuple(dict(record.metadata) for record in corrupted_candidate.source_records)
        with self.assertRaisesRegex(
            ValueError, "Promotion state lacks trusted exact-source evidence"
        ):
            validate_candidate_partition_integrity((corrupted_candidate,))
        self.assertEqual(
            tuple(dict(record.metadata) for record in corrupted_candidate.source_records),
            before,
        )
        corrupted = replace(valid, candidates=valid.candidates)
        object.__setattr__(corrupted, "candidates", (corrupted_candidate,))
        with tempfile.TemporaryDirectory() as directory:
            repository = SQLiteResearchUniverseRepository(
                Path(directory) / "bad-promoted-candidate-identity.sqlite"
            )
            with self.assertRaisesRegex(
                ValueError, "Promotion state lacks trusted exact-source evidence"
            ):
                repository.save(corrupted)

    def test_untrusted_imported_promotion_like_provenance_has_no_merge_authority(self):
        original = source_record({
            "company_name": "Unrelated", "ticker": "ZS",
            "identity_status": "unresolved", "candidate_identity": "candidate:same",
        }, UniverseSource.RCE_GENERATED, source_reference="rce:unrelated")
        imported = source_record({
            "company_name": "Zscaler Inc.", "ticker": "ZS",
            "identity_status": "resolved",
            "membership_provenance": [{
                "source": "promoted_candidate",
                "source_identity": "candidate:same",
                "source_reference": "rce:unrelated",
            }],
        }, UniverseSource.IMPORTED, source_reference="import:zs")

        universe = self.service.assemble(
            universe_id="untrusted-import", title="Untrusted import",
            starting_companies=(imported,), rce_suggestions=(original,),
        )

        self.assertEqual(
            {row.normalized_matching_key for row in universe.candidates
             if not row.normalized_matching_key.startswith("name:unrelated:evidence:")},
            {"ticker:ZS"},
        )
        self.assertEqual(sum(
            row.normalized_matching_key.startswith("name:unrelated:evidence:")
            for row in universe.candidates
        ), 1)
        self.assertEqual(
            sum(len(row.source_records) for row in universe.candidates), 2
        )

    def test_malformed_and_imported_promotion_metadata_cannot_merge(self):
        original = source_record({
            "company_name": "Zscaler", "ticker": "ZS",
            "identity_status": "unresolved", "candidate_identity": "candidate:zscaler",
        }, UniverseSource.RCE_GENERATED, source_reference="rce:zscaler")
        for source, link in (
            (UniverseSource.USER_ENTERED, {"type": "research_universe_promotion"}),
            (UniverseSource.IMPORTED, {
                "type": "research_universe_promotion", "version": 1,
                "workflow": "validated_manual_resolution",
                "candidate_identity": "candidate:zscaler",
                "original_source_reference": "rce:zscaler",
                "expected_name_key": "zscaler", "expected_raw_ticker": "ZS",
                "promoted_security_id": None, "promoted_ticker": "ZS",
                "validation_result": "valid",
            }),
        ):
            promoted = source_record({
                "company_name": "Zscaler Inc.", "ticker": "ZS",
                "identity_status": "resolved", "identity_validation_status": "valid",
                "trusted_promotion_reference": link,
            }, source, source_reference="session:forged:suggestion-promotion")
            with self.assertRaisesRegex(ValueError, "Promotion state lacks trusted"):
                self.service.assemble(
                    universe_id=f"forged-{source.value}", title="Forged",
                    starting_companies=(promoted,), rce_suggestions=(original,),
                )

    def test_partition_integrity_rejects_unsupported_canonical_fields_and_flags(self):
        universe = self.assemble(starting=(source_record({
            "company_name": "Alpha", "ticker": "AAA", "identity_status": "resolved",
        }, UniverseSource.USER_ENTERED, source_reference="manual:aaa"),))
        candidate = universe.candidates[0]
        invalid_cases = (
            (replace(candidate, normalized_matching_key="ticker:ZZZ"),
             "Ticker canonical identity lacks"),
            (replace(candidate, normalized_matching_key="security:SEC9"),
             "Security canonical identity lacks"),
            (replace(candidate, identity_status=IdentityStatus.UNRESOLVED),
             "Unresolved candidates require"),
            (replace(candidate, in_starting_companies=False),
             "Starting-company flag"),
            (replace(candidate, in_rce_suggestions=True),
             "RCE flag"),
        )
        for invalid, message in invalid_cases:
            with self.assertRaisesRegex(ValueError, message):
                validate_candidate_partition_integrity((invalid,))

        unresolved_evidence = source_record({
            "company_name": "Unknown", "ticker": "UNK",
            "identity_status": "unresolved",
        }, UniverseSource.USER_ENTERED, source_reference="manual:unknown")
        unresolved_candidate = replace(
            candidate,
            normalized_matching_key="ticker:UNK",
            company_name="Unknown",
            ticker_or_identifier="UNK",
            identity_status=IdentityStatus.RESOLVED,
            source_records=(unresolved_evidence,),
        )
        with self.assertRaisesRegex(ValueError, "Ticker canonical identity lacks"):
            validate_candidate_partition_integrity((unresolved_candidate,))

    def test_partition_integrity_is_non_mutating_and_rejects_duplicate_ownership(self):
        universe = self.assemble(
            starting=(source_record({
                "company_name": "Alpha", "ticker": "AAA",
                "identity_status": "resolved",
            }, UniverseSource.USER_ENTERED, source_reference="manual:aaa"),),
            rce=(source_record({
                "company_name": "Beta", "ticker": "BBB",
                "identity_status": "resolved",
            }, UniverseSource.RCE_GENERATED, source_reference="rce:bbb"),),
        )
        before = self._canonical_signature(universe)
        before_metadata = tuple(
            dict(record.metadata)
            for candidate in universe.candidates
            for record in candidate.source_records
        )
        validate_candidate_partition_integrity(universe.candidates)
        self.assertEqual(self._canonical_signature(universe), before)
        self.assertEqual(tuple(
            dict(record.metadata)
            for candidate in universe.candidates
            for record in candidate.source_records
        ), before_metadata)

        duplicate = replace(
            universe.candidates[1],
            source_records=(universe.candidates[0].source_records[0],),
            normalized_matching_key="ticker:AAA",
            ticker_or_identifier="AAA",
            in_starting_companies=True,
            in_rce_suggestions=False,
        )
        with self.assertRaisesRegex(ValueError, "unique canonical identities|multiple candidates"):
            validate_candidate_partition_integrity(
                (universe.candidates[0], duplicate)
            )

    def test_partition_integrity_rejects_contradictory_ambiguous_display(self):
        universe = self.assemble(starting=(source_record({
            "company_name": "Alpha", "ticker": "AAA",
            "identity_status": "resolved",
        }, UniverseSource.USER_ENTERED, source_reference="manual:aaa"),))
        contradictory = replace(
            universe.candidates[0],
            identity_status=IdentityStatus.AMBIGUOUS,
            ticker_or_identifier="WRONG",
        )

        with self.assertRaisesRegex(
            ValueError, "Ambiguous.*contradictory evidence"
        ):
            validate_candidate_partition_integrity((contradictory,))
        corrupted = replace(universe, candidates=(universe.candidates[0],))
        object.__setattr__(corrupted, "candidates", (contradictory,))
        with tempfile.TemporaryDirectory() as directory:
            repository = SQLiteResearchUniverseRepository(
                Path(directory) / "ambiguous.sqlite"
            )
            with self.assertRaisesRegex(
                ValueError, "Ambiguous.*contradictory evidence"
            ):
                repository.save(corrupted)

    def test_partition_integrity_rejects_mismatched_evidence_discriminator(self):
        universe = self.assemble(starting=(source_record({
            "company_name": "Same Co", "ticker": "AAA",
        }, UniverseSource.USER_ENTERED, source_reference="manual:same"),))
        candidate = universe.candidates[0]
        invalid_keys = (
            "name:sameco:evidence:",
            "name:sameco:evidence:not-a-valid-discriminator",
            "name:sameco:evidence:0000000000000000",
            "name:sameco",
        )
        for invalid_key in invalid_keys:
            invalid = replace(candidate, normalized_matching_key=invalid_key)
            with self.subTest(key=invalid_key), self.assertRaisesRegex(
                ValueError, "does not match owned evidence"
            ):
                validate_candidate_partition_integrity((invalid,))

        other = self.assemble(starting=(source_record({
            "company_name": "Same Co", "ticker": "AAA",
        }, UniverseSource.USER_ENTERED, source_reference="manual:other"),))
        copied = replace(
            candidate,
            normalized_matching_key=other.candidates[0].normalized_matching_key,
        )
        with self.assertRaisesRegex(ValueError, "does not match owned evidence"):
            validate_candidate_partition_integrity((copied,))

        corrupted = replace(universe, candidates=(candidate,))
        object.__setattr__(
            corrupted, "candidates",
            (replace(candidate, normalized_matching_key=invalid_keys[2]),),
        )
        with tempfile.TemporaryDirectory() as directory:
            repository = SQLiteResearchUniverseRepository(
                Path(directory) / "bad-discriminator.sqlite"
            )
            with self.assertRaisesRegex(ValueError, "does not match owned evidence"):
                repository.save(corrupted)

    def test_repository_save_revalidates_partition_without_repair(self):
        universe = self.assemble(starting=(source_record({
            "company_name": "Alpha", "ticker": "AAA", "identity_status": "resolved",
        }, UniverseSource.USER_ENTERED, source_reference="manual:aaa"),))
        object.__setattr__(
            universe,
            "candidates",
            (replace(
                universe.candidates[0],
                normalized_matching_key="ticker:ZZZ",
            ),),
        )
        with tempfile.TemporaryDirectory() as directory:
            repository = SQLiteResearchUniverseRepository(
                Path(directory) / "invalid.sqlite"
            )
            with self.assertRaisesRegex(ValueError, "Ticker canonical identity lacks"):
                repository.save(universe)
            self.assertFalse((Path(directory) / "invalid.sqlite").exists())

    def test_promotion_linkage_cannot_attach_an_unrelated_raw_ticker_candidate(self):
        unresolved = source_record(
            {
                "company_name": "Unrelated Company", "ticker": "ZS",
                "identity_status": IdentityStatus.UNRESOLVED,
                "candidate_identity": "candidate:unrelated",
            },
            UniverseSource.RCE_GENERATED, source_reference="rce:unrelated",
        )
        promoted = source_record(
            {
                "company_name": "Zscaler Inc.", "ticker": "ZS",
                "identity_status": IdentityStatus.RESOLVED,
                "candidate_identity": "candidate:zscaler",
                "membership_provenance": [{
                    "source": "promoted_candidate",
                    "source_identity": "candidate:zscaler",
                    "source_reference": "manual:zs",
                }],
            },
            UniverseSource.USER_ENTERED, source_reference="manual:zs",
        )
        universe = self.assemble(starting=(promoted,), rce=(unresolved,))

        self.assertEqual(
            {row.normalized_matching_key for row in universe.candidates
             if not row.normalized_matching_key.startswith(
                 "name:unrelatedcompany:evidence:"
             )},
            {"ticker:ZS"},
        )
        self.assertEqual(sum(
            row.normalized_matching_key.startswith(
                "name:unrelatedcompany:evidence:"
            )
            for row in universe.candidates
        ), 1)
        self.assertEqual(sum(len(row.source_records) for row in universe.candidates), 2)

    def test_manual_canonical_name_promotes_suggestion_without_fuzzy_matching(self):
        universe = self.assemble(rce=(record("Zscaler, Inc.", "ZS", UniverseSource.RCE_GENERATED),))
        manual = source_record(
            {"company_name": "Zscaler", "supplied_value": "Zscaler"},
            UniverseSource.USER_ENTERED, source_reference="manual:zscaler",
        )
        revised = self.service.revise(universe, additional_starting_companies=(manual,))
        self.assertEqual(len(revised.approved_membership), 1)
        promoted = revised.approved_membership[0]
        self.assertEqual(promoted.ticker_or_identifier, "ZS")
        self.assertEqual(promoted.identity_status, IdentityStatus.RESOLVED)
        self.assertEqual(
            {row.source_reference for row in promoted.source_records},
            {"manual:zscaler", "rce_generated:test"},
        )
        misspelled = source_record(
            {"company_name": "zscalar", "supplied_value": "zscalar"}, UniverseSource.USER_ENTERED,
        )
        separate = self.service.revise(universe, additional_starting_companies=(misspelled,))
        self.assertEqual(len(separate.candidates), 2)
        self.assertEqual(separate.approved_membership[0].identity_status, IdentityStatus.UNRESOLVED)

    def test_unresolved_historical_coherent_evidence_stays_separate_from_cohr(self):
        cohr = source_record(
            {
                "company_name": "Coherent Corp", "ticker": "COHR",
                "identity_status": IdentityStatus.RESOLVED,
            },
            UniverseSource.USER_ENTERED, source_reference="manual:cohr",
        )
        csg = source_record(
            {
                "company_name": "Coherent, Inc.",
                "raw_ticker_or_identifier": "CSG",
                "identity_status": IdentityStatus.UNRESOLVED,
                "identity_validation_status": "unresolved",
                "candidate_identity_validation": {
                    "validation_status": "unresolved",
                    "raw_company_name": "Coherent, Inc.",
                    "raw_ticker_or_identifier": "CSG",
                    "normalized_ticker_or_identifier": None,
                },
            },
            UniverseSource.RCE_GENERATED, source_reference="rce:coherent-csg",
        )

        universe = self.assemble(starting=(cohr,), rce=(csg,))
        by_key = {row.normalized_matching_key: row for row in universe.candidates}
        csg_key = next(
            key for key in by_key if key.startswith("name:coherentinc:evidence:")
        )
        discriminator = csg_key.removeprefix("name:coherentinc:evidence:")

        self.assertEqual(set(by_key), {"ticker:COHR", csg_key})
        self.assertTrue(discriminator)
        self.assertEqual(by_key["ticker:COHR"].identity_status, IdentityStatus.RESOLVED)
        self.assertEqual(by_key["ticker:COHR"].source_records, (cohr,))
        self.assertNotEqual(by_key[csg_key].identity_status, IdentityStatus.RESOLVED)
        self.assertEqual(by_key[csg_key].source_records, (csg,))
        self.assertEqual(
            sum(len(candidate.source_records) for candidate in universe.candidates), 2
        )
        self.assertEqual(len({
            id(record)
            for candidate in universe.candidates
            for record in candidate.source_records
        }), 2)
        self.assertNotEqual(
            by_key["ticker:COHR"].disposition,
            by_key[csg_key].disposition,
        )
        other_starting = source_record(
            {"company_name": "Other Start", "supplied_value": "Other Start"},
            UniverseSource.USER_ENTERED, source_reference="manual:other",
        )
        other_rce = source_record(
            {"company_name": "Other Suggestion", "ticker": "OTHR"},
            UniverseSource.RCE_GENERATED, source_reference="rce:other",
        )
        ordered = self.service.assemble(
            universe_id="ordered-coherent", title="Ordered coherent",
            starting_companies=(cohr, other_starting),
            rce_suggestions=(csg, other_rce),
        )
        repeated = self.service.assemble(
            universe_id="reverse-coherent", title="Reverse coherent",
            starting_companies=(other_starting, cohr),
            rce_suggestions=(other_rce, csg),
        )
        ordered_csg_key = next(
            row.normalized_matching_key for row in ordered.candidates
            if row.source_records == (csg,)
        )
        repeated_csg_key = next(
            row.normalized_matching_key for row in repeated.candidates
            if row.source_records == (csg,)
        )
        self.assertEqual(ordered_csg_key, repeated_csg_key)
        self.assertEqual(repeated_csg_key, csg_key)
        self.assertEqual(
            tuple(
                (row.normalized_matching_key, row.source_records)
                for row in repeated.candidates
            ),
            tuple(
                (row.normalized_matching_key, row.source_records)
                for row in ordered.candidates
            ),
        )

    def test_canonical_groups_have_exclusive_source_ownership_and_unique_identities(self):
        manual = source_record(
            {"company_name": "Zscaler", "supplied_value": "Zscaler"},
            UniverseSource.USER_ENTERED, source_reference="manual:zscaler",
        )
        suggestion = record("Zscaler, Inc.", "ZS", UniverseSource.RCE_GENERATED)
        other = record("CrowdStrike", "CRWD", UniverseSource.RCE_GENERATED)
        universe = self.assemble(starting=(manual,), rce=(suggestion, other))

        keys = [row.normalized_matching_key for row in universe.candidates]
        owned = [
            id(source)
            for candidate in universe.candidates
            for source in candidate.source_records
        ]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertEqual(len(owned), len(set(owned)))
        self.assertEqual(sum(len(row.source_records) for row in universe.candidates), 3)

    def test_canonical_grouping_is_input_order_deterministic(self):
        starting = (
            record("Beta", "BBB", UniverseSource.USER_ENTERED),
            source_record(
                {"company_name": "Zscaler", "supplied_value": "Zscaler"},
                UniverseSource.USER_ENTERED, source_reference="manual:zscaler",
            ),
        )
        suggestions = (
            record("Alpha", "AAA", UniverseSource.RCE_GENERATED),
            record("Zscaler, Inc.", "ZS", UniverseSource.RCE_GENERATED),
        )

        first = self.assemble(starting=starting, rce=suggestions)
        second = self.assemble(
            starting=tuple(reversed(starting)),
            rce=tuple(reversed(suggestions)),
        )

        self.assertEqual(self._canonical_signature(first), self._canonical_signature(second))

    def test_persistence_round_trip_is_exact_and_does_not_multiply_evidence(self):
        manual = source_record(
            {"company_name": "Zscaler", "supplied_value": "Zscaler"},
            UniverseSource.USER_ENTERED, source_reference="manual:zscaler",
        )
        universe = self.assemble(
            starting=(manual,),
            rce=(record("Zscaler, Inc.", "ZS", UniverseSource.RCE_GENERATED),),
        )
        with tempfile.TemporaryDirectory() as directory:
            repository = SQLiteResearchUniverseRepository(Path(directory) / "research.sqlite")
            repository.save(universe)
            first = repository.get(universe.universe_id)
            repository.save(first)
            second = repository.get(universe.universe_id)

        self.assertEqual(self._canonical_signature(first), self._canonical_signature(universe))
        self.assertEqual(self._canonical_signature(second), self._canonical_signature(universe))
        self.assertEqual(first.candidates[0].identity_status, IdentityStatus.RESOLVED)
        self.assertEqual(len(first.candidates[0].source_records), 2)
        self.assertEqual(len(second.candidates[0].source_records), 2)

    def test_repeated_reassembly_preserves_resolved_confidence_and_evidence(self):
        universe = self.assemble(
            starting=(record(
                "Alpha", "AAA", UniverseSource.USER_ENTERED,
                identity_status=IdentityStatus.RESOLVED,
            ),),
            rce=(record(
                "Alpha, Inc.", "AAA", UniverseSource.RCE_GENERATED,
                identity_status=IdentityStatus.RESOLVED,
            ),),
        )
        first = self.service.revise(universe)
        second = self.service.revise(first)

        self.assertEqual(self._canonical_signature(first), self._canonical_signature(second))
        self.assertEqual(second.candidates[0].identity_status, IdentityStatus.RESOLVED)
        self.assertEqual(len(second.candidates[0].source_records), 2)

    def test_research_universe_construction_rejects_duplicate_canonical_identity(self):
        universe = self.assemble(
            starting=(record("Alpha", "AAA", UniverseSource.USER_ENTERED),),
        )
        with self.assertRaisesRegex(ValueError, "unique canonical identities"):
            universe.__class__(
                universe_id=universe.universe_id,
                title=universe.title,
                research_question=universe.research_question,
                state=universe.state,
                version=universe.version,
                candidates=(universe.candidates[0], universe.candidates[0]),
                created_at=universe.created_at,
                updated_at=universe.updated_at,
            )

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
        _, first_records = ResearchUniverseInputService().resolve(
            "crwd, CRWD", source_reference="session:universe-1:manual",
        )
        _, repeated_records = ResearchUniverseInputService().resolve(
            "CRWD", source_reference="session:universe-1:manual",
        )
        revised = self.service.revise(
            universe,
            additional_starting_companies=(*first_records, *repeated_records),
        )
        self.assertEqual(len(revised.approved_membership), 1)
        self.assertEqual(len(revised.approved_membership[0].source_records), 1)

    def test_same_unresolved_ticker_with_distinct_sources_remains_separate(self):
        first = source_record(
            {"company_name": "AAA", "ticker": "AAA"},
            UniverseSource.USER_ENTERED, source_reference="manual:first",
        )
        second = source_record(
            {"company_name": "AAA", "ticker": "AAA"},
            UniverseSource.USER_ENTERED, source_reference="manual:second",
        )

        universe = self.assemble(starting=(first, second))

        self.assertEqual(len(universe.candidates), 2)
        self.assertEqual(
            {record.source_reference
             for candidate in universe.candidates
             for record in candidate.source_records},
            {"manual:first", "manual:second"},
        )

    def test_manual_add_overrides_prior_rejection_as_explicit_membership(self):
        suggestion = record("Zscaler", "ZS", UniverseSource.RCE_GENERATED)
        key = normalized_matching_key("Zscaler", "ZS")
        universe = self.assemble(rce=(suggestion,), decisions={key: CandidateDisposition.REJECTED})
        manual = source_record({"company_name": "ZS", "ticker": "ZS", "supplied_value": "ZS"}, UniverseSource.USER_ENTERED)
        revised = self.service.revise(universe, additional_starting_companies=(manual,))
        self.assertEqual(revised.approved_membership[0].ticker_or_identifier, "ZS")

    def test_unresolved_same_ticker_addition_does_not_reset_other_group_disposition(self):
        suggestion = source_record({
            "company_name": "Validated Co", "ticker": "AAA",
            "identity_status": "resolved",
        }, UniverseSource.RCE_GENERATED, source_reference="rce:validated")
        universe = self.assemble(
            rce=(suggestion,),
            decisions={"ticker:AAA": CandidateDisposition.REJECTED},
        )
        unrelated = source_record({
            "company_name": "Unrelated Co", "ticker": "AAA",
            "identity_status": "unresolved",
        }, UniverseSource.USER_ENTERED, source_reference="manual:unrelated")

        revised = self.service.revise(
            universe, additional_starting_companies=(unrelated,)
        )
        by_key = {candidate.normalized_matching_key: candidate for candidate in revised.candidates}

        self.assertEqual(
            by_key["ticker:AAA"].disposition, CandidateDisposition.REJECTED
        )
        self.assertEqual(
            next(candidate for key, candidate in by_key.items() if key.startswith("name:")).disposition,
            CandidateDisposition.INCLUDED,
        )

    def test_remove_members_preserves_source_history(self):
        universe = self.assemble((record("Manual", None, UniverseSource.USER_ENTERED),))
        key = universe.approved_membership[0].normalized_matching_key
        revised = self.service.remove_members(universe, (key,))
        self.assertEqual(revised.approved_membership, ())
        self.assertEqual(revised.candidates[0].disposition, CandidateDisposition.REJECTED)
        self.assertEqual(revised.candidates[0].source_records[0].company_name, "Manual")

    def test_downstream_handoff_is_exact_and_does_not_run_analysis(self):
        universe = self.assemble(
            (record(
                "Alpha", "AAA", UniverseSource.USER_ENTERED,
                identity_status=IdentityStatus.RESOLVED,
            ),),
            (record(
                "Alpha", "AAA", UniverseSource.RCE_GENERATED,
                identity_status=IdentityStatus.RESOLVED,
            ),),
        )
        handoff = universe.downstream_handoff()
        self.assertEqual(handoff.universe_id, "universe-1")
        self.assertEqual(handoff.universe_version, 1)
        self.assertEqual(handoff.approved_constituents, ("AAA",))
        self.assertEqual(handoff.expected_constituent_count, len(handoff.approved_constituents))

    def test_shared_review_rows_are_mode_independent(self):
        universe = self.assemble(
            (record(
                "Alpha", "AAA", UniverseSource.USER_ENTERED,
                identity_status=IdentityStatus.RESOLVED,
            ),),
            (record(
                "Alpha", "AAA", UniverseSource.RCE_GENERATED,
                identity_status=IdentityStatus.RESOLVED,
            ),),
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

    @staticmethod
    def _canonical_signature(universe):
        return tuple(
            (
                candidate.normalized_matching_key,
                candidate.company_name,
                candidate.ticker_or_identifier,
                candidate.identity_status,
                candidate.disposition,
                tuple(
                    (
                        source.source, source.company_name,
                        source.ticker_or_identifier, source.source_reference,
                        source.identity_status, source.original_input,
                        json.dumps(dict(source.metadata), sort_keys=True),
                    )
                    for source in candidate.source_records
                ),
            )
            for candidate in universe.candidates
        )


if __name__ == "__main__":
    unittest.main()
