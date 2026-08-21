"""Application orchestration for deterministic Universe Analysis presentation."""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from src.universe_analysis_change_detection import (
    UniverseChangeDetectionResultV01,
    detect_universe_changes,
)
from src.universe_analysis_contracts import UniverseAnalysisSnapshotV1
from src.universe_analysis_snapshot_comparison import (
    Comparability,
    SnapshotComparisonAssessmentV01,
    assess_snapshot_comparability,
)
from src.universe_analysis_snapshot_repository import UniverseAnalysisSnapshotRepository
from src.universe_interpretation_input import (
    UniverseInterpretationInputV01,
    build_universe_interpretation_input_v01,
)
from src.universe_interpretation_presentation import (
    InterpretationPresentationContractV01,
    build_interpretation_presentation_v01,
)
from src.universe_interpretation_selection import (
    InterpretationSelectionResultV01,
    select_universe_interpretation_facts_v01,
)


class PresentationAssemblyStatus(StrEnum):
    READY = "ready"
    FIRST_SNAPSHOT = "first_snapshot"
    CURRENT_SNAPSHOT_UNAVAILABLE = "current_snapshot_unavailable"


@dataclass(frozen=True, slots=True)
class BaselineCandidateDiagnosticV01:
    snapshot_id: str
    comparability: str
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class UniverseAnalysisPresentationBundleV01:
    status: PresentationAssemblyStatus
    current_snapshot: UniverseAnalysisSnapshotV1 | None
    baseline_snapshot: UniverseAnalysisSnapshotV1 | None
    comparison: SnapshotComparisonAssessmentV01 | None
    changes: UniverseChangeDetectionResultV01 | None
    interpretation_input: UniverseInterpretationInputV01 | None
    selection: InterpretationSelectionResultV01 | None
    presentation: InterpretationPresentationContractV01 | None
    candidate_diagnostics: tuple[BaselineCandidateDiagnosticV01, ...]


def build_universe_analysis_presentation(
    current_snapshot_id: str,
    repository: UniverseAnalysisSnapshotRepository,
) -> UniverseAnalysisPresentationBundleV01:
    """Resolve history and invoke the existing deterministic pipeline end to end."""
    current = repository.get(current_snapshot_id)
    if current is None:
        return _empty(PresentationAssemblyStatus.CURRENT_SNAPSHOT_UNAVAILABLE)

    history = repository.list_for_universe(current.universe_id)
    current_index = next((index for index, item in enumerate(history)
                          if item.snapshot_id == current.snapshot_id), None)
    candidates = history[current_index + 1:] if current_index is not None else ()
    if not candidates:
        return UniverseAnalysisPresentationBundleV01(
            PresentationAssemblyStatus.FIRST_SNAPSHOT, current, None, None, None,
            None, None, None, (),
        )

    assessed = tuple((candidate, assess_snapshot_comparability(candidate, current))
                     for candidate in candidates)
    baseline, comparison = _select_baseline(assessed)
    diagnostics = tuple(BaselineCandidateDiagnosticV01(
        candidate.snapshot_id, assessment.comparability.value, assessment.reasons,
    ) for candidate, assessment in assessed)
    changes = detect_universe_changes(baseline, current, comparison)
    case_file = build_universe_interpretation_input_v01(
        baseline, current, comparison, changes,
    )
    selection = select_universe_interpretation_facts_v01(case_file)
    presentation = build_interpretation_presentation_v01(selection)
    return UniverseAnalysisPresentationBundleV01(
        PresentationAssemblyStatus.READY, current, baseline, comparison, changes,
        case_file, selection, presentation, diagnostics,
    )


def _select_baseline(assessed):
    """Prefer the newest full candidate, then limited, then explicit not-comparable."""
    for level in (Comparability.FULL, Comparability.LIMITED, Comparability.NOT_COMPARABLE):
        for candidate, assessment in assessed:
            if assessment.comparability == level:
                return candidate, assessment
    raise ValueError("Snapshot history did not produce a comparison assessment.")


def _empty(status):
    return UniverseAnalysisPresentationBundleV01(
        status, None, None, None, None, None, None, None, (),
    )
