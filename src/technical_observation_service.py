"""Application boundary for archiving technical observations and derived Signals."""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Callable, Iterable

from src.research_repository import (
    ResearchRepository,
    research_repository_from_target,
    research_repository_target_from_env,
)
from src.signal_repository import SignalRepository
from src.signals import technical_setup_signal, volatility_context_signal


_URI_CREDENTIALS = re.compile(r"(?P<scheme>[a-z][a-z0-9+.-]*://)(?P<userinfo>[^/@\s]+)@", re.I)


def safe_diagnostic_detail(error: object) -> str:
    """Retain useful exception context while removing URI credentials."""
    detail = f"{type(error).__name__}: {error}" if isinstance(error, BaseException) else str(error)
    return _URI_CREDENTIALS.sub(r"\g<scheme><credentials>@", detail)


@dataclass(frozen=True, slots=True)
class TechnicalObservationPersistenceResult:
    archive_result: Any
    technical_observation_count: int
    signal_inserted_count: int
    signal_retry_count: int
    signal_persistence_error: str | None = None

    @property
    def signals_persisted(self) -> bool:
        return self.signal_persistence_error is None


def configured_technical_observation_repositories(
    env: dict[str, str] | None = None,
) -> tuple[ResearchRepository, SignalRepository]:
    """Build both repositories from one resolved target."""
    target = research_repository_target_from_env(env)
    return research_repository_from_target(target), SignalRepository(target)


def archive_technical_observations_and_signals(
    technical_rows: Iterable[dict[str, Any]],
    *,
    archive_observations: Callable[[tuple[dict[str, Any], ...]], Any],
    signal_repository: SignalRepository,
) -> TechnicalObservationPersistenceResult:
    """Archive observations first, then atomically persist their derived Signals."""
    rows = tuple(technical_rows)
    archive_result = archive_observations(rows)
    if not rows:
        return TechnicalObservationPersistenceResult(
            archive_result=archive_result,
            technical_observation_count=0,
            signal_inserted_count=0,
            signal_retry_count=0,
            signal_persistence_error=(
                "No successfully generated technical observations were available "
                "for derived Signal persistence."
            ),
        )
    try:
        signals = []
        for row in rows:
            signals.append(technical_setup_signal(row))
            if isinstance(row.get("_volatility_context"), dict):
                signals.append(volatility_context_signal(row))
        inserted = signal_repository.save_signals(signals)
    except Exception as error:
        return TechnicalObservationPersistenceResult(
            archive_result=archive_result,
            technical_observation_count=len(rows),
            signal_inserted_count=0,
            signal_retry_count=0,
            signal_persistence_error=safe_diagnostic_detail(error),
        )
    return TechnicalObservationPersistenceResult(
        archive_result=archive_result,
        technical_observation_count=len(rows),
        signal_inserted_count=sum(inserted),
        signal_retry_count=len(inserted) - sum(inserted),
    )
