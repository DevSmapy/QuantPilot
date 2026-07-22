"""Tests for application settings."""

from __future__ import annotations

import pytest

from quantpilot.config import get_settings, reset_settings


def test_get_settings_is_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    reset_settings()
    monkeypatch.setenv("OLLAMA_MODEL", "cached-model")

    first = get_settings()
    second = get_settings()

    assert first is second
    assert first.ollama_model == "cached-model"
    reset_settings()


def test_reset_settings_creates_fresh_instance(monkeypatch: pytest.MonkeyPatch) -> None:
    reset_settings()
    monkeypatch.setenv("OLLAMA_MODEL", "first-model")
    first = get_settings()

    reset_settings()
    monkeypatch.setenv("OLLAMA_MODEL", "second-model")
    second = get_settings()

    assert first is not second
    assert second.ollama_model == "second-model"
    reset_settings()
