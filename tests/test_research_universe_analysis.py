from datetime import datetime
from zoneinfo import ZoneInfo

from src.research_universe import ResearchUniverseReviewService, UniverseSource, source_record
from src.research_universe_analysis import (
    AnalysisMemberStatus,
    execute_research_universe_analysis,
    preflight_research_universe,
)


class FakeMarketData:
    def __init__(self, unavailable=()):
        self.unavailable = set(unavailable)
        self.history_requests = []

    def get_price_history(self, symbol, **kwargs):
        self.history_requests.append(symbol)
        if symbol in self.unavailable:
            return {"history": {"day": []}}
        return {"history": {"day": [{"close": 100 + index / 10} for index in range(260)]}}

    def get_quote(self, symbol):
        return {"quotes": {"quote": {"symbol": symbol, "last": 125}}}


class FakeRepository:
    def __init__(self):
        self.archives = []

    def archive_technical_observations(self, **kwargs):
        self.archives.append(kwargs)
        return {"technical_characterization": len(kwargs["technical_rows"])}


def _universe(symbols):
    return ResearchUniverseReviewService().assemble(
        universe_id="cyber-8", title="Cybersecurity", research_question="Which companies secure modern infrastructure?",
        starting_companies=tuple(source_record(
            {"company_name": symbol, "ticker": symbol, "identity_status": "resolved"},
            UniverseSource.CURATOR_AUTHORED, source_reference=f"source:{symbol}",
        ) for symbol in symbols),
        version=4,
    )


def test_exact_eight_member_preflight_keeps_invalid_identifier_explicit():
    symbols = ("CHKP", "CRWD", "FTNT", "OKTA", "PANW", "S", "ZS-AI", "ZS")
    handoff = _universe(symbols).downstream_handoff()
    client = FakeMarketData()
    preflight = preflight_research_universe(handoff, client)

    assert handoff.universe_id == "cyber-8"
    assert handoff.universe_version == 4
    assert tuple(member.ticker_or_identifier for member in handoff.ordered_members) == tuple(
        row.ticker_or_identifier for row in _universe(symbols).approved_membership
    )
    assert len(preflight.ledger) == handoff.total_member_count == 8
    assert preflight.analyzable_tickers == ("CHKP", "CRWD", "FTNT", "OKTA", "PANW", "S", "ZS")
    invalid = next(row for row in preflight.ledger if row.ticker_or_identifier == "ZS-AI")
    assert invalid.status == AnalysisMemberStatus.UNSUPPORTED
    assert "ZS-AI" not in client.history_requests


def test_execution_creates_new_exact_run_and_reconciled_ledger():
    symbols = ("CHKP", "CRWD", "FTNT", "OKTA", "PANW", "S", "ZS-AI", "ZS")
    client = FakeMarketData()
    preflight = preflight_research_universe(_universe(symbols).downstream_handoff(), client)
    repository = FakeRepository()
    run = execute_research_universe_analysis(
        preflight, client=client, repository=repository,
        now=datetime(2026, 7, 20, 12, 0, tzinfo=ZoneInfo("America/New_York")),
    )

    assert run.scan_id.startswith("research-universe-20260720-120000-")
    assert run.universe_id == "cyber-8" and run.universe_version == 4
    assert run.requested_constituent_count == 8
    assert run.requested_tickers == ("CHKP", "CRWD", "FTNT", "OKTA", "PANW", "S", "ZS")
    assert run.analyzed_tickers == run.requested_tickers
    assert run.unavailable_tickers == ("ZS-AI",)
    assert len(run.ledger) == 8
    assert sum(row.status == AnalysisMemberStatus.ANALYZED for row in run.ledger) == 7
    assert sum(row.status == AnalysisMemberStatus.UNSUPPORTED for row in run.ledger) == 1
    assert repository.archives[0]["scan_id"] == run.scan_id
    assert {row["ticker"] for row in repository.archives[0]["technical_rows"]} == set(run.requested_tickers)


def test_no_market_data_is_not_silently_requested_for_execution():
    client = FakeMarketData(unavailable={"BAD"})
    preflight = preflight_research_universe(_universe(("CRWD", "BAD")).downstream_handoff(), client)
    assert preflight.analyzable_tickers == ("CRWD",)
    bad = next(row for row in preflight.ledger if row.ticker_or_identifier == "BAD")
    assert bad.status == AnalysisMemberStatus.NO_MARKET_DATA


def test_new_research_runs_are_isolated_and_never_reuse_scan_or_membership():
    client = FakeMarketData()
    repository = FakeRepository()
    now = datetime(2026, 7, 20, 12, 0, tzinfo=ZoneInfo("America/New_York"))
    run_a = execute_research_universe_analysis(
        preflight_research_universe(_universe(("CRWD",)).downstream_handoff(), client),
        client=client, repository=repository, now=now,
    )
    universe_b = ResearchUniverseReviewService().assemble(
        universe_id="universe-b", title="B",
        starting_companies=(source_record(
            {"company_name": "PANW", "ticker": "PANW", "identity_status": "resolved"},
            UniverseSource.CURATOR_AUTHORED,
        ),),
    )
    run_b = execute_research_universe_analysis(
        preflight_research_universe(universe_b.downstream_handoff(), client),
        client=client, repository=repository, now=now,
    )
    assert run_a.scan_id != run_b.scan_id
    assert run_a.requested_tickers == ("CRWD",)
    assert run_b.universe_id == "universe-b" and run_b.requested_tickers == ("PANW",)


def test_historical_scan_browsing_is_explicit_compatibility_only():
    source = open("src/universe_analysis_page.py", encoding="utf-8").read()
    assert "Historical scans (compatibility only)" in source
    assert "Historical data below does not redefine" in source
    assert "historical scans are not substituted" in source


def test_marvell_mrvl_is_ready_for_the_current_market_data_path():
    universe = ResearchUniverseReviewService().assemble(
        universe_id="marvell-test", title="AI networking",
        starting_companies=(source_record(
            {"company_name": "Marvell Technology", "ticker": "MRVL", "identity_status": "resolved"},
            UniverseSource.USER_ENTERED,
            source_reference="session:marvell-test:manual",
        ),),
    )

    preflight = preflight_research_universe(universe.downstream_handoff(), FakeMarketData())

    assert preflight.analyzable_tickers == ("MRVL",)
    assert preflight.ledger[0].status == AnalysisMemberStatus.READY
