"""Append-only administrative provenance for Research Universe QA.

The event file is diagnostic-only and is never rendered in the user experience.
"""
from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from enum import Enum
import json
import os
from pathlib import Path
from typing import Any, Mapping


DIAGNOSTIC_PATH_ENV = "RESEARCH_UNIVERSE_DIAGNOSTIC_PATH"


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return _json_safe(asdict(value))
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        return _json_safe(model_dump(mode="json"))
    return str(value)


class ResearchUniverseDiagnosticStore:
    """Write reconstructable lifecycle events without changing product state."""

    def __init__(self, path: str | Path | None = None):
        configured = path or os.getenv(DIAGNOSTIC_PATH_ENV)
        self.path = Path(configured) if configured else Path("logs/research_universe_provenance.jsonl")

    def append(self, event_type: str, *, request_run_id: str, universe_id: str, universe_version: int, payload: Mapping[str, Any]) -> dict[str, Any]:
        event = {
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "request_run_id": request_run_id,
            "universe_id": universe_id,
            "universe_version": universe_version,
            "payload": _json_safe(payload),
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")
        return event


def raw_provider_artifact(raw_response: Any) -> Any:
    """Return the fullest safely serializable provider response already available."""
    return _json_safe(raw_response)
