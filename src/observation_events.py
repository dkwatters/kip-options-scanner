"""Immutable, deterministic changes between version-compatible Signals."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import json
from typing import Any, Mapping
from uuid import NAMESPACE_URL, uuid5
from zoneinfo import ZoneInfo

from src.signals import Signal, SignalDirection, SignalFamily


OBSERVATION_EVENT_SCHEMA_VERSION = "observation-event.v0.1"
OBSERVATION_EVENT_RULES_VERSION = "signal-transition-rules-v0.1"


class ObservationEventImportance(str, Enum):
    INFORMATIONAL = "informational"
    NOTABLE = "notable"
    MAJOR = "major"


@dataclass(frozen=True, slots=True)
class ObservationEvent:
    event_id: str
    ticker: str
    observed_at: str
    signal_family: SignalFamily
    model_id: str
    model_version: str
    event_type: str
    prior_signal_id: str
    current_signal_id: str
    prior_as_of: str
    current_as_of: str
    field: str
    prior_value: Any
    current_value: Any
    importance: ObservationEventImportance
    components: Mapping[str, Any] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)
    source_scan_id: str | None = None
    created_at: str = ""
    schema_version: str = OBSERVATION_EVENT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in (
            "event_id", "ticker", "observed_at", "model_id", "model_version",
            "event_type", "prior_signal_id", "current_signal_id", "prior_as_of",
            "current_as_of", "field", "created_at", "schema_version",
        ):
            if not str(getattr(self, name)).strip():
                raise ValueError(f"{name} is required")
        object.__setattr__(self, "ticker", self.ticker.strip().upper())
        object.__setattr__(self, "signal_family", SignalFamily(self.signal_family))
        object.__setattr__(self, "importance", ObservationEventImportance(self.importance))
        if self.prior_signal_id == self.current_signal_id:
            raise ValueError("an observation event requires two distinct signals")
        if signal_instant(self.prior_as_of) >= signal_instant(self.current_as_of):
            raise ValueError("prior_as_of must be strictly earlier than current_as_of")


_DIRECTIONAL_TREND_ORDER = {
    "bearish_alignment": 0, "deteriorating": 1, "mixed": 2,
    "constructive": 3, "bullish_alignment": 4,
}
_VOLATILITY_REGIME_ORDER = {"quiet": 0, "normal": 1, "elevated": 2, "extreme": 3}


def detect_observation_events(prior: Signal, current: Signal) -> tuple[ObservationEvent, ...]:
    """Compare one strictly earlier Signal to a matching current Signal."""
    identity = (prior.ticker, prior.signal_family, prior.model_id, prior.model_version)
    if identity != (current.ticker, current.signal_family, current.model_id, current.model_version):
        return ()
    if signal_instant(prior.as_of) >= signal_instant(current.as_of):
        return ()
    changes: list[tuple[str, str, Any, Any, ObservationEventImportance]] = []
    if current.signal_family is SignalFamily.DIRECTIONAL:
        before = _state(prior.metadata.get("source_trend_state"))
        after = _state(current.metadata.get("source_trend_state"))
        if before and after and before != after:
            distance = abs(_DIRECTIONAL_TREND_ORDER.get(after, 0) - _DIRECTIONAL_TREND_ORDER.get(before, 0))
            changes.append(("directional.trend_state_changed", "trend_state", before, after,
                            ObservationEventImportance.MAJOR if distance >= 2 else ObservationEventImportance.NOTABLE))
        if prior.direction is not current.direction:
            opposed = {prior.direction, current.direction} == {SignalDirection.BULLISH, SignalDirection.BEARISH}
            changes.append(("directional.direction_changed", "direction", prior.direction.value,
                            current.direction.value, ObservationEventImportance.MAJOR if opposed else ObservationEventImportance.NOTABLE))
    elif current.signal_family is SignalFamily.VOLATILITY:
        before = _state(prior.metadata.get("regime")); after = _state(current.metadata.get("regime"))
        if before and after and before != after:
            distance = abs(_VOLATILITY_REGIME_ORDER.get(after, 0) - _VOLATILITY_REGIME_ORDER.get(before, 0))
            changes.append(("volatility.regime_changed", "regime", before, after,
                            ObservationEventImportance.MAJOR if distance >= 2 else ObservationEventImportance.NOTABLE))
        before = _state(prior.metadata.get("volatility_trend")); after = _state(current.metadata.get("volatility_trend"))
        if before and after and before != after:
            changes.append(("volatility.trend_changed", "volatility_trend", before, after,
                            ObservationEventImportance.NOTABLE))
    return tuple(_event(prior, current, *change) for change in changes)


def _event(prior: Signal, current: Signal, event_type: str, field_name: str,
           before: Any, after: Any, importance: ObservationEventImportance) -> ObservationEvent:
    identity = json.dumps(
        [OBSERVATION_EVENT_SCHEMA_VERSION, prior.signal_id, current.signal_id, event_type, field_name],
        separators=(",", ":"),
    )
    source_scan_id = str(current.metadata.get("source_scan_id") or "").strip() or None
    return ObservationEvent(
        event_id=str(uuid5(NAMESPACE_URL, identity)), ticker=current.ticker,
        observed_at=current.as_of, signal_family=current.signal_family,
        model_id=current.model_id, model_version=current.model_version,
        event_type=event_type, prior_signal_id=prior.signal_id,
        current_signal_id=current.signal_id, prior_as_of=prior.as_of,
        current_as_of=current.as_of, field=field_name, prior_value=before,
        current_value=after, importance=importance,
        components={"field": field_name, "prior": before, "current": after},
        metadata={
            "rules_version": OBSERVATION_EVENT_RULES_VERSION,
            "prior_evidence_refs": list(prior.evidence_refs),
            "current_evidence_refs": list(current.evidence_refs),
            "prior_source_scan_id": prior.metadata.get("source_scan_id"),
            "current_source_scan_id": current.metadata.get("source_scan_id"),
            "directional_interpretation": current.signal_family is SignalFamily.DIRECTIONAL,
        },
        source_scan_id=source_scan_id, created_at=current.created_at,
    )


def _state(value: Any) -> str:
    return str(value or "").strip().lower()


def signal_instant(value: str) -> datetime:
    """Normalize the repository's ISO and legacy Eastern display timestamps."""
    raw = str(value).strip()
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        timestamp_without_zone = raw.rsplit(" ", 1)[0]
        parsed = datetime.strptime(timestamp_without_zone, "%Y-%m-%d %I:%M:%S %p").replace(
            tzinfo=ZoneInfo("America/New_York")
        )
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
