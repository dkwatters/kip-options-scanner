from __future__ import annotations

import pytest
from fastapi import HTTPException

import api


def test_v01_exposes_only_intended_research_universe_routes():
    routes = {
        (route.path, frozenset(route.methods or ()))
        for route in api.app.routes
        if route.path.startswith("/api/") or route.path == "/health"
    }
    assert routes == {
        ("/health", frozenset({"GET"})),
        ("/api/v1/universes", frozenset({"GET"})),
        ("/api/v1/universes/{universe_id}", frozenset({"GET"})),
        ("/api/v1/universes", frozenset({"POST"})),
    }


def test_health_is_available_without_repository_or_credentials():
    assert api.health() == {"status": "ok", "api_version": "0.1.0"}


def test_authentication_fails_closed_when_key_is_not_configured(monkeypatch):
    monkeypatch.delenv("RESEARCH_API_KEY", raising=False)
    with pytest.raises(HTTPException) as caught:
        api._authorize("Bearer anything")
    assert caught.value.status_code == 503


def test_authentication_accepts_only_exact_bearer_secret(monkeypatch):
    monkeypatch.setenv("RESEARCH_API_KEY", "test-secret")
    api._authorize("Bearer test-secret")
    with pytest.raises(HTTPException) as caught:
        api._authorize("Bearer wrong-secret")
    assert caught.value.status_code == 401
