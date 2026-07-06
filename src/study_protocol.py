"""Study Protocol metadata for repeatable observational research scans."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from src.evaluation_profile import DEFAULT_EVALUATION_PROFILE


RUN_MODE_MANUAL_UI = "manual-ui"
RUN_MODE_RESEARCH_SCRIPT = "research-script"
RUN_MODE_SCHEDULED = "scheduled"

RunMode = Literal["manual-ui", "research-script", "scheduled"]


@dataclass(frozen=True, slots=True)
class StudyProtocol:
    study_id: str
    study_name: str
    study_version: str
    study_purpose: str
    evaluation_profile_name: str
    evaluation_profile_version: str
    universe_csv: Path
    option_type: str
    dte_min: int
    dte_max: int
    suggested_schedule_times_et: tuple[str, ...]

    def metadata(
        self,
        scheduled_time_label: str | None = None,
        run_mode: RunMode = RUN_MODE_MANUAL_UI,
    ) -> dict[str, str | None]:
        return {
            "study_id": self.study_id,
            "study_name": self.study_name,
            "study_version": self.study_version,
            "study_purpose": self.study_purpose,
            "scheduled_time_label": scheduled_time_label,
            "run_mode": run_mode,
        }


DEFAULT_STUDY_PROTOCOL = StudyProtocol(
    study_id="SP-001",
    study_name="Intraday Technology Growth AI Calls",
    study_version="v0.1",
    study_purpose=(
        "Characterize intraday behavior of the Contract Quality Model and "
        "Technology Growth / Momentum AI universe."
    ),
    evaluation_profile_name=DEFAULT_EVALUATION_PROFILE.name,
    evaluation_profile_version=DEFAULT_EVALUATION_PROFILE.version,
    universe_csv=Path("data/technology_growth_ai_v1.csv"),
    option_type="Calls",
    dte_min=7,
    dte_max=28,
    suggested_schedule_times_et=("10:00", "12:00", "14:00"),
)


TAM_STUDY_PROTOCOL = StudyProtocol(
    study_id="TAM-001",
    study_name="Daily Technical Characterization",
    study_version="v0.1",
    study_purpose="Collect daily stock-level technical observations.",
    evaluation_profile_name=DEFAULT_EVALUATION_PROFILE.name,
    evaluation_profile_version=DEFAULT_EVALUATION_PROFILE.version,
    universe_csv=Path("data/technology_growth_ai_v1.csv"),
    option_type="N/A",
    dte_min=0,
    dte_max=0,
    suggested_schedule_times_et=("16:30",),
)
