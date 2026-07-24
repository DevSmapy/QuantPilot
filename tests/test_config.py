"""Tests for application settings."""

from __future__ import annotations

from pathlib import Path

import pytest

from quantpilot.config import Settings, get_settings, reset_settings, running_in_docker


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


def test_local_falls_back_to_qseed_host_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("quantpilot.config.running_in_docker", lambda: False)
    host = tmp_path / "qseed"
    host.mkdir()
    missing = tmp_path / "missing-container-mount"

    settings = Settings(
        _env_file=None,
        qseed_data_path=missing,
        qseed_host_path=host,
        ollama_base_url="http://ollama:11434",
    )

    assert settings.qseed_data_path == host
    assert settings.ollama_base_url == "http://localhost:11434"


def test_docker_keeps_container_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("quantpilot.config.running_in_docker", lambda: True)
    host = tmp_path / "qseed"
    host.mkdir()
    container = tmp_path / "data-qseed"
    container.mkdir()

    settings = Settings(
        _env_file=None,
        qseed_data_path=container,
        qseed_host_path=host,
        ollama_base_url="http://ollama:11434",
    )

    assert settings.qseed_data_path == container
    assert settings.ollama_base_url == "http://ollama:11434"


def test_running_in_docker_false_on_host(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("QUANTPILOT_IN_DOCKER", raising=False)

    class _MissingDockerEnv:
        def exists(self) -> bool:
            return False

    def path_factory(value: str = "") -> object:
        if value == "/.dockerenv":
            return _MissingDockerEnv()
        return Path(value)

    monkeypatch.setattr("quantpilot.config.Path", path_factory)
    assert running_in_docker() is False
