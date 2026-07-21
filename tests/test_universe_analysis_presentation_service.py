from dataclasses import replace

import pytest

from src.universe_analysis_presentation_service import (
    PresentationAssemblyStatus,
    build_universe_analysis_presentation,
)
from src.universe_analysis_streamlit_adapter import (
    build_universe_analysis_streamlit_view_model,
    resolve_caveat_label,
    resolve_display_label,
)
from tests.test_universe_analysis_change_detection import _pair


class Repository:
    def __init__(self, snapshots):
        self.snapshots = tuple(snapshots)

    def get(self, snapshot_id):
        return next((item for item in self.snapshots if item.snapshot_id == snapshot_id), None)

    def list_for_universe(self, universe_id, universe_version=None):
        return tuple(item for item in self.snapshots if item.universe_id == universe_id
                     and (universe_version is None or item.universe_version == universe_version))


def test_first_snapshot_is_explicit_and_does_not_manufacture_comparison():
    _, current = _pair()
    result = build_universe_analysis_presentation(current.snapshot_id, Repository((current,)))
    assert result.status == PresentationAssemblyStatus.FIRST_SNAPSHOT
    assert result.current_snapshot is current
    assert result.comparison is result.changes is result.presentation is None


def test_missing_current_snapshot_is_typed_not_exception():
    result = build_universe_analysis_presentation("missing", Repository(()))
    assert result.status == PresentationAssemblyStatus.CURRENT_SNAPSHOT_UNAVAILABLE


def test_fully_comparable_pipeline_and_view_model_are_end_to_end_deterministic():
    baseline, current = _pair(field="technical_profile", before="Weak", after="Strong")
    repository = Repository((current, baseline))
    first = build_universe_analysis_presentation(current.snapshot_id, repository)
    second = build_universe_analysis_presentation(current.snapshot_id, repository)
    assert first == second and first.status == PresentationAssemblyStatus.READY
    assert first.comparison.comparability.value == "fully_comparable"
    assert first.changes.atomic_events and first.interpretation_input and first.selection and first.presentation
    view = build_universe_analysis_streamlit_view_model(first)
    assert [section.key for section in view.sections] == [section.name.value for section in first.presentation.sections]
    changed = view.section("what_changed").rows[0]
    assert (changed.previous_value, changed.current_value) == ("Weak", "Strong")
    assert changed.event_type and changed.evidence_refs


def test_newest_full_baseline_is_preferred_over_newer_incompatible_candidate():
    baseline, current = _pair(field="momentum", before="neutral", after="positive")
    incompatible = replace(baseline, snapshot_id="newer-incompatible",
                           version_manifest=replace(baseline.version_manifest,
                                                    technical_analysis_version="other"))
    result = build_universe_analysis_presentation(
        current.snapshot_id, Repository((current, incompatible, baseline)),
    )
    assert result.baseline_snapshot.snapshot_id == baseline.snapshot_id
    assert [item.comparability for item in result.candidate_diagnostics] == [
        "not_comparable", "fully_comparable",
    ]


def test_limited_membership_pipeline_preserves_addition_removal_and_rank_safety():
    baseline, current = _pair()
    added = replace(current.members[-1], matching_key="ticker:NEW", member_snapshot_id="new-member",
                    ticker_or_identifier="NEW", company_name="New Company")
    current = replace(current, universe_version=4, membership_digest="changed",
                      members=current.members[:-1] + (added,))
    result = build_universe_analysis_presentation(current.snapshot_id, Repository((current, baseline)))
    assert result.comparison.comparability.value == "limited_comparability"
    assert not result.comparison.rank_comparison_allowed
    membership = build_universe_analysis_streamlit_view_model(result).section("membership_changes").rows
    assert [row.event_type for row in membership] == ["membership_added", "membership_removed"]


def test_not_comparable_pipeline_keeps_caveats_and_suppresses_changes():
    baseline, current = _pair()
    baseline = replace(baseline, version_manifest=replace(
        baseline.version_manifest, technical_analysis_version="legacy",
    ))
    result = build_universe_analysis_presentation(current.snapshot_id, Repository((current, baseline)))
    view = build_universe_analysis_streamlit_view_model(result)
    assert result.comparison.comparability.value == "not_comparable"
    assert view.section("what_changed").rows == ()
    assert view.section("caveats").rows


def test_leader_laggard_attention_and_overflow_order_comes_from_presentation():
    baseline, current = _pair(field="technical_profile", before="Weak", after="Strong")
    result = build_universe_analysis_presentation(current.snapshot_id, Repository((current, baseline)))
    view = build_universe_analysis_streamlit_view_model(result)
    assert [row.source_identity for row in view.section("leaders").rows] == [
        slot.item.source_identity for slot in result.presentation.section("leaders").slots
    ]
    assert [row.source_identity for row in view.section("laggards").rows] == [
        slot.item.source_identity for slot in result.presentation.section("laggards").slots
    ]
    assert view.section("deserves_attention").rows
    assert all(section.omitted_item_count >= 0 for section in view.sections)


@pytest.mark.parametrize("key,label", [
    ("leader_position", "Leader position"),
    ("change_event_type", "Change event"),
    ("future_stable_key", "Future stable key"),
])
def test_label_resolution_is_bounded_and_safe(key, label):
    assert resolve_display_label(key) == label
    assert resolve_caveat_label("members_unavailable") == "One or more universe members are unavailable"


def test_service_and_adapter_have_no_provider_ai_or_streamlit_dependency():
    for path in ("src/universe_analysis_presentation_service.py",
                 "src/universe_analysis_streamlit_adapter.py"):
        source = open(path, encoding="utf-8").read().lower()
        assert "tradier" not in source and "openai" not in source
    assert "import streamlit" not in open(
        "src/universe_analysis_streamlit_adapter.py", encoding="utf-8"
    ).read().lower()
