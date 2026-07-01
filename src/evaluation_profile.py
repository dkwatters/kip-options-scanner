"""Evaluation Profile metadata for analytical workflows.

An Evaluation Profile is the configuration context used to evaluate a
Universe and produce an Opportunity Scan. This module only represents the
current default profile; it does not introduce profile selection or new models.
"""
from dataclasses import dataclass, field
from typing import Any, Mapping

from src.universe import CURRENT_UNIVERSE_NAME


@dataclass(frozen=True, slots=True)
class ModelReference:
    """Name a model that belongs to an Evaluation Profile."""

    name: str
    version: str


@dataclass(frozen=True, slots=True)
class EvaluationProfile:
    """Configuration context for running analytical workflows."""

    name: str
    version: str
    universe_name: str
    contract_quality_model: ModelReference
    technical_model: ModelReference | None = None
    trade_fit_model: ModelReference | None = None
    default_scan_parameters: Mapping[str, Any] = field(default_factory=dict)
    ranking_preferences: Mapping[str, Any] = field(default_factory=dict)
    output_preferences: Mapping[str, Any] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)


DEFAULT_EVALUATION_PROFILE = EvaluationProfile(
    name="Default Momentum Growth",
    version="v0.1",
    universe_name=CURRENT_UNIVERSE_NAME,
    contract_quality_model=ModelReference(
        name="Contract Quality Model",
        version="v0.1",
    ),
    technical_model=None,
    trade_fit_model=None,
    default_scan_parameters={
        "option_type": "Calls",
        "min_dte": 7,
        "max_dte": 28,
    },
    ranking_preferences={
        "primary_order": "quality_score_desc",
        "fallback_status": "true_near_miss",
    },
    output_preferences={
        "diagnostics": "qed",
    },
    metadata={
        "description": "Default Momentum Growth v0.1",
    },
)


def evaluation_profile_export_fields(
    profile: EvaluationProfile = DEFAULT_EVALUATION_PROFILE,
) -> dict[str, str]:
    """Return stable Opportunity Scan metadata for exports."""
    return {
        "evaluation_profile_name": profile.name,
        "evaluation_profile_version": profile.version,
        "contract_quality_model_name": profile.contract_quality_model.name,
        "contract_quality_model_version": profile.contract_quality_model.version,
    }
