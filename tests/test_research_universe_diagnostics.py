import json

from src.research_universe_diagnostics import ResearchUniverseDiagnosticStore, raw_provider_artifact


class ProviderResponse:
    def model_dump(self, *, mode):
        assert mode == "json"
        return {"id": "response-123", "output_text": "exact provider text"}


def test_diagnostic_store_archives_reconstructable_append_only_events(tmp_path):
    path = tmp_path / "diagnostics" / "provenance.jsonl"
    store = ResearchUniverseDiagnosticStore(path)
    store.append(
        "rce_response_parsed",
        request_run_id="request-1",
        universe_id="universe-1",
        universe_version=2,
        payload={
            "raw_provider_response": raw_provider_artifact(ProviderResponse()),
            "parsed_candidates": [{"company_name": "Marvell Technology", "ticker": "MRVL"}],
        },
    )
    store.append(
        "suggestion_promoted",
        request_run_id="request-1",
        universe_id="universe-1",
        universe_version=2,
        payload={"ticker": "MRVL", "identity_resolution": "resolved"},
    )

    events = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert [event["event_type"] for event in events] == [
        "rce_response_parsed", "suggestion_promoted",
    ]
    assert events[0]["request_run_id"] == "request-1"
    assert events[0]["payload"]["raw_provider_response"]["output_text"] == "exact provider text"
    assert events[0]["payload"]["parsed_candidates"][0] == {
        "company_name": "Marvell Technology", "ticker": "MRVL",
    }
