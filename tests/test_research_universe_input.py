import unittest

from src.research_universe import IdentityStatus, ResearchUniverseReviewService, UniverseSource, source_record
from src.research_universe_input import ResearchUniverseInputService, parse_ticker_input
from src.research_universe_review_page import promote_suggested_candidate


class ResearchUniverseInputTest(unittest.TestCase):
    def test_csv_newline_case_empty_and_duplicates_share_one_normalization(self):
        compact = parse_ticker_input("CRWD,PANW,ZS")
        spaced = parse_ticker_input(" crwd, PANW, , zs\nCRWD ")
        self.assertEqual(tuple(row.ticker for row in compact.entries), ("CRWD", "PANW", "ZS"))
        self.assertEqual(tuple(row.ticker for row in spaced.entries), ("CRWD", "PANW", "ZS"))

    def test_free_form_company_name_is_rejected_not_guessed(self):
        parsed = parse_ticker_input("CrowdStrike")
        self.assertEqual(parsed.entries, ())
        self.assertEqual(parsed.invalid_values, ("CrowdStrike",))

    def test_known_metadata_resolves_and_unknown_ticker_shape_does_not(self):
        known = source_record(
            {"company_name": "Zscaler, Inc.", "ticker": "ZS", "identity_status": "resolved"},
            UniverseSource.RCE_GENERATED,
            source_reference="rce:cybersecurity",
        )
        _, records = ResearchUniverseInputService().resolve(
            "zs, ZZUNKNOWN", source_reference="manual:test", known_records=(known,),
        )
        self.assertEqual(records[0].company_name, "Zscaler, Inc.")
        self.assertEqual(records[0].identity_status, IdentityStatus.RESOLVED)
        self.assertEqual(records[1].identity_status, IdentityStatus.UNRESOLVED)

    def test_manual_promotion_preserves_rce_and_explicit_provenance(self):
        suggestion = source_record(
            {"company_name": "Zscaler, Inc.", "ticker": "ZS", "identity_status": "resolved"},
            UniverseSource.RCE_GENERATED,
            source_reference="rce:cybersecurity",
        )
        service = ResearchUniverseReviewService()
        universe = service.assemble(universe_id="u", title="U", rce_suggestions=(suggestion,))
        _, additions = ResearchUniverseInputService().resolve(
            "ZS", source_reference="manual:u", known_records=(suggestion,),
        )
        promoted = service.revise(universe, additional_starting_companies=additions)
        member = promoted.approved_membership[0]
        self.assertEqual(member.company_name, "Zscaler, Inc.")
        self.assertEqual(member.identity_status, IdentityStatus.RESOLVED)
        self.assertEqual(promoted.progress.pending, 0)
        self.assertEqual({row.source for row in member.source_records}, {
            UniverseSource.RCE_GENERATED, UniverseSource.USER_ENTERED,
        })

    def test_rejected_suggestion_can_be_promoted_idempotently(self):
        suggestion = source_record(
            {"company_name": "Zscaler", "ticker": "ZS", "identity_status": "resolved"},
            UniverseSource.RCE_GENERATED,
        )
        service = ResearchUniverseReviewService()
        universe = service.assemble(universe_id="u", title="U", rce_suggestions=(suggestion,))
        key = universe.candidates[0].normalized_matching_key
        rejected = service.revise(universe, dispositions={key: "rejected"})
        _, additions = ResearchUniverseInputService().resolve(
            "zs, ZS", source_reference="manual:u", known_records=(suggestion,),
        )
        promoted = service.revise(rejected, additional_starting_companies=additions)
        self.assertEqual(len(promoted.approved_membership), 1)
        self.assertEqual(promoted.approved_membership[0].ticker_or_identifier, "ZS")

    def test_market_lookup_never_substitutes_a_different_symbol(self):
        class Lookup:
            def get_quote(self, symbol):
                return {"quotes": {"quote": {"symbol": "OTHER", "description": "Other"}}}

        _, records = ResearchUniverseInputService(Lookup()).resolve(
            "ABC.F", source_reference="manual:foreign",
        )
        self.assertEqual(records[0].ticker_or_identifier, "ABC.F")
        self.assertEqual(records[0].identity_status, IdentityStatus.UNRESOLVED)
        self.assertEqual(records[0].metadata["identity_diagnostic"], "market_data_symbol_not_confirmed")

    def test_market_lookup_records_deterministic_failure_diagnostic(self):
        class Lookup:
            def get_quote(self, symbol):
                raise TimeoutError("provider details must not leak into identity state")

        _, records = ResearchUniverseInputService(Lookup()).resolve(
            "ZZFAKE", source_reference="suggestion:test",
        )
        self.assertEqual(records[0].company_name, "ZZFAKE")
        self.assertEqual(records[0].ticker_or_identifier, "ZZFAKE")
        self.assertEqual(records[0].identity_status, IdentityStatus.UNRESOLVED)
        self.assertEqual(records[0].metadata["identity_diagnostic"], "market_data_error:TimeoutError")

    def test_promoted_valid_suggestion_resolves_and_deduplicates_by_ticker(self):
        class Lookup:
            def get_quote(self, symbol):
                return {"quotes": {"quote": {"symbol": symbol, "description": "Zscaler Inc."}}}

        suggestion = source_record(
            {
                "company_name": "Zscaler", "ticker": "ZS",
                "identity_status": "unresolved",
                "candidate_identity": "candidate:zscaler",
            },
            UniverseSource.RCE_GENERATED,
            source_reference="session:rce-enrichment:candidate:zscaler",
        )
        universe = ResearchUniverseReviewService().assemble(
            universe_id="u", title="U", rce_suggestions=(suggestion,),
        )
        promoted = promote_suggested_candidate(
            universe, universe.candidates[0].normalized_matching_key,
            ResearchUniverseInputService(Lookup()),
        )
        self.assertEqual(len(promoted.candidates), 1)
        member = promoted.approved_membership[0]
        self.assertEqual((member.company_name, member.ticker_or_identifier), ("Zscaler Inc.", "ZS"))
        self.assertEqual(member.identity_status, IdentityStatus.RESOLVED)
        self.assertEqual(len(member.source_records), 2)
        self.assertEqual(
            {row.metadata.get("candidate_identity") for row in member.source_records},
            {"candidate:zscaler"},
        )

    def test_source_less_unresolved_suggestion_cannot_receive_trusted_promotion(self):
        class Lookup:
            def get_quote(self, symbol):
                return {
                    "quotes": {
                        "quote": {
                            "symbol": symbol,
                            "description": "Zscaler Inc.",
                        }
                    }
                }

        suggestion = source_record(
            {
                "company_name": "Zscaler", "ticker": "ZS",
                "identity_status": "unresolved",
                "candidate_identity": "candidate:zscaler",
            },
            UniverseSource.RCE_GENERATED,
        )
        universe = ResearchUniverseReviewService().assemble(
            universe_id="legacy-source-less", title="Source-less",
            rce_suggestions=(suggestion,),
        )

        promoted = promote_suggested_candidate(
            universe, universe.candidates[0].normalized_matching_key,
            ResearchUniverseInputService(Lookup()),
        )

        self.assertEqual(len(promoted.candidates), 2)
        self.assertFalse(any(
            "trusted_promotion_reference" in record.metadata
            for candidate in promoted.candidates
            for record in candidate.source_records
        ))

    def test_promoted_fabricated_suggestion_remains_unresolved_with_diagnostics(self):
        class Lookup:
            def get_quote(self, symbol):
                return {"quotes": {"quote": {"symbol": "OTHER"}}}

        suggestion = source_record(
            {"company_name": "Imaginary AI Cloud", "ticker": "FAKEAI", "identity_status": "unresolved"},
            UniverseSource.RCE_GENERATED,
        )
        universe = ResearchUniverseReviewService().assemble(
            universe_id="u", title="U", rce_suggestions=(suggestion,),
        )
        promoted = promote_suggested_candidate(
            universe, universe.candidates[0].normalized_matching_key,
            ResearchUniverseInputService(Lookup()),
        )
        member = promoted.approved_membership[0]
        self.assertEqual((member.company_name, member.ticker_or_identifier), ("Imaginary AI Cloud", "FAKEAI"))
        self.assertEqual(member.identity_status, IdentityStatus.UNRESOLVED)
        self.assertIn(
            "market_data_symbol_not_confirmed",
            [record.metadata.get("identity_diagnostic") for record in member.source_records],
        )

    def test_launchpad_and_ru_use_equivalent_shared_service_outcomes(self):
        from src.research_universe_builder_page import _manual_records

        known = source_record(
            {"company_name": "CrowdStrike Holdings", "ticker": "CRWD", "identity_status": "resolved"},
            UniverseSource.RCE_GENERATED,
        )
        launchpad = _manual_records("crwd, UNKNOWN", "launchpad", known_records=(known,))
        _, ru = ResearchUniverseInputService().resolve(
            "crwd, UNKNOWN", source_reference="manual:ru", known_records=(known,),
        )
        self.assertEqual(
            tuple((row.company_name, row.ticker_or_identifier, row.identity_status) for row in launchpad),
            tuple((row.company_name, row.ticker_or_identifier, row.identity_status) for row in ru),
        )

    def test_marvell_mrvl_promotes_ready_without_ticker_substitution(self):
        class Lookup:
            def get_quote(self, symbol):
                return {"quotes": {"quote": {
                    "symbol": "MRVL", "description": "Marvell Technology, Inc.",
                }}}

        suggestion = source_record(
            {"company_name": "Marvell Technology", "ticker": "MRVL", "identity_status": "unresolved"},
            UniverseSource.RCE_GENERATED,
            source_reference="session:rce-suggestions",
        )
        universe = ResearchUniverseReviewService().assemble(
            universe_id="marvell-test", title="AI networking", rce_suggestions=(suggestion,),
        )

        promoted = promote_suggested_candidate(
            universe, universe.candidates[0].normalized_matching_key,
            ResearchUniverseInputService(Lookup()),
        )

        member = promoted.approved_membership[0]
        self.assertEqual(member.ticker_or_identifier, "MRVL")
        self.assertEqual(member.identity_status, IdentityStatus.RESOLVED)

    def test_marvell_with_incorrect_ticker_is_not_silently_ready(self):
        class Lookup:
            def get_quote(self, symbol):
                return {"quotes": {"quote": {
                    "symbol": "MRVL", "description": "Marvell Technology, Inc.",
                }}}

        _, records = ResearchUniverseInputService(Lookup()).resolve(
            "MRVLBAD", source_reference="session:marvell-test:suggestion-promotion",
        )

        self.assertEqual(records[0].ticker_or_identifier, "MRVLBAD")
        self.assertEqual(records[0].identity_status, IdentityStatus.UNRESOLVED)
        self.assertEqual(records[0].metadata["identity_diagnostic"], "market_data_symbol_not_confirmed")


if __name__ == "__main__":
    unittest.main()
