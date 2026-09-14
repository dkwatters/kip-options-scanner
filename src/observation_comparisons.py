"""Versioned, immutable first-observation comparison evidence."""
from dataclasses import dataclass
from typing import Any, Mapping
from uuid import NAMESPACE_URL, uuid5
import json

from src.observation_events import _freeze_json, event_json_value, signal_instant
from src.signals import SignalFamily

COMPARISON_SCHEMA_VERSION = "observation-comparison.v0.1"
COMPARISON_POLICY_VERSION = "first-observation.v0.1"


def comparison_identity(current_signal_id: str, policy_version: str = COMPARISON_POLICY_VERSION) -> str:
    return str(uuid5(NAMESPACE_URL, json.dumps(
        [COMPARISON_SCHEMA_VERSION, policy_version, current_signal_id], separators=(",", ":"),
    )))


@dataclass(frozen=True, slots=True)
class ObservationComparison:
    comparison_id: str
    current_signal_id: str
    prior_signal_id: str | None
    ticker: str
    signal_family: SignalFamily
    model_id: str
    model_version: str
    current_as_of: str
    prior_as_of: str | None
    evaluated_at: str
    event_count: int
    source_scan_id: str | None
    metadata: Mapping[str, Any]
    created_at: str
    policy_version: str = COMPARISON_POLICY_VERSION
    schema_version: str = COMPARISON_SCHEMA_VERSION

    def __post_init__(self):
        for name in ("current_signal_id", "ticker", "model_id", "model_version",
                     "current_as_of", "evaluated_at", "created_at", "policy_version"):
            if not str(getattr(self, name)).strip():
                raise ValueError(f"{name} is required")
        object.__setattr__(self, "signal_family", SignalFamily(self.signal_family))
        object.__setattr__(self, "metadata", _freeze_json(self.metadata))
        if self.comparison_id != comparison_identity(self.current_signal_id, self.policy_version):
            raise ValueError("Comparison identity does not match current Signal and policy")
        if self.schema_version != COMPARISON_SCHEMA_VERSION:
            raise ValueError("Unsupported comparison schema")
        if self.event_count < 0:
            raise ValueError("event_count must be nonnegative")
        if len(self.metadata.get("event_ids", ())) != self.event_count:
            raise ValueError("event_count must match reserved event identities")
        if (self.prior_signal_id is None) != (self.prior_as_of is None):
            raise ValueError("Prior identity and timestamp must both be present or absent")
        if self.prior_as_of is None and self.event_count:
            raise ValueError("No-prior comparisons cannot produce events")
        if self.prior_as_of is not None and signal_instant(self.prior_as_of) >= signal_instant(self.current_as_of):
            raise ValueError("Comparison prior must be strictly earlier")


COMPARISON_COLUMNS = tuple(ObservationComparison.__dataclass_fields__)


def comparison_values(comparison):
    values = dict((name, getattr(comparison, name)) for name in COMPARISON_COLUMNS)
    values["signal_family"] = comparison.signal_family.value
    values["metadata"] = json.dumps(event_json_value(comparison.metadata), sort_keys=True, separators=(",", ":"))
    return tuple(values.values())


def comparison_from_row(row):
    values = dict(zip(COMPARISON_COLUMNS, row, strict=True))
    values["metadata"] = json.loads(values["metadata"])
    return ObservationComparison(**values)


# Portable additive DDL; both backends use the same immutable comparison and completion receipt.
COMPARISON_DDL = (
    """CREATE TABLE IF NOT EXISTS observation_comparisons (
    comparison_id TEXT PRIMARY KEY,
    current_signal_id TEXT NOT NULL REFERENCES research_signals(signal_id),
    prior_signal_id TEXT REFERENCES research_signals(signal_id),
    ticker TEXT NOT NULL, signal_family TEXT NOT NULL, model_id TEXT NOT NULL,
    model_version TEXT NOT NULL, current_as_of TEXT NOT NULL, prior_as_of TEXT,
    evaluated_at TEXT NOT NULL, event_count INTEGER NOT NULL CHECK(event_count >= 0),
    source_scan_id TEXT, metadata TEXT NOT NULL, created_at TEXT NOT NULL,
    policy_version TEXT NOT NULL, schema_version TEXT NOT NULL,
    UNIQUE(current_signal_id, policy_version))""",
    "CREATE INDEX IF NOT EXISTS idx_observation_comparisons_model ON observation_comparisons(ticker, signal_family, model_id, model_version)",
    """CREATE TABLE IF NOT EXISTS observation_comparison_completions (
    comparison_id TEXT PRIMARY KEY REFERENCES observation_comparisons(comparison_id))""",
)
