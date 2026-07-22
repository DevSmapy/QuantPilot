"""Tests for OllamaProvider."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest

from quantpilot.ai.ollama_provider import OllamaProvider
from quantpilot.exceptions import OllamaConnectionError


def test_ollama_provider_review_strategy() -> None:
    provider = OllamaProvider(base_url="http://localhost:11434", model="llama3.1:8b")
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {"response": "전략 리뷰 결과입니다."}

    with patch("httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.__exit__.return_value = None
        mock_client.post.return_value = mock_response
        mock_client_cls.return_value = mock_client

        review = provider.review_strategy(
            strategy_name="SMA Cross",
            metrics={"cagr": 0.12, "mdd": -0.08},
            summary="Fast/slow SMA crossover on single asset.",
        )

    assert review == "전략 리뷰 결과입니다."
    mock_client.post.assert_called_once()


def test_ollama_provider_generate_json_format() -> None:
    provider = OllamaProvider(base_url="http://localhost:11434", model="llama3.2")
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {
        "response": '{"action":"hold","size":0,"reason":"wait"}'
    }

    with patch("httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.__exit__.return_value = None
        mock_client.post.return_value = mock_response
        mock_client_cls.return_value = mock_client

        text = provider.generate(
            "prompt",
            format_json=True,
            options={"seed": 1, "temperature": 0.5},
        )

    assert "hold" in text
    payload = mock_client.post.call_args.kwargs["json"]
    assert payload["format"] == "json"
    assert payload["options"] == {"seed": 1, "temperature": 0.5}


def test_ollama_provider_empty_response_error() -> None:
    from quantpilot.exceptions import OllamaResponseError

    provider = OllamaProvider(base_url="http://localhost:11434", model="llama3.2")
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {"response": "  "}

    with patch("httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.__exit__.return_value = None
        mock_client.post.return_value = mock_response
        mock_client_cls.return_value = mock_client

        with pytest.raises(OllamaResponseError):
            provider.generate("prompt")



def test_ollama_provider_connection_error() -> None:
    provider = OllamaProvider()

    with patch("httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.__exit__.return_value = None
        mock_client.post.side_effect = httpx.ConnectError("connection failed")
        mock_client_cls.return_value = mock_client

        with pytest.raises(OllamaConnectionError):
            provider.review_strategy("SMA Cross", {}, "summary")
