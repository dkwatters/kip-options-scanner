"""Keep environment-selected repository writes isolated during pytest runs."""

import pytest


@pytest.fixture(autouse=True)
def isolate_default_research_repository(monkeypatch, tmp_path):
    monkeypatch.setenv("RESEARCH_REPOSITORY_BACKEND", "sqlite")
    monkeypatch.setenv("RESEARCH_SQLITE_PATH", str(tmp_path / "default-research.sqlite"))
