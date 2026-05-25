"""Tests fuer backend.routers.models_router — Weiterleitung von /models/pull und DELETE /models/{name} an Ollama."""
from __future__ import annotations

import json
from unittest.mock import patch, AsyncMock, MagicMock
import pytest
from fastapi.testclient import TestClient

from backend.main import app


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


class FakeClient:
    def __init__(self, base_url: str):
        self.base_url = base_url

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


@pytest.mark.anyio
async def test_pull_model_lmstudio_fallback(client):
    """Wenn der Provider LM Studio ist (keine 11434 im Port), wird ein 501 zurückgegeben."""
    fake_client = FakeClient("http://127.0.0.1:1234/v1")
    
    with patch("backend.routers.models_router._make_alive_client", AsyncMock(return_value=(fake_client, True, False))):
        response = client.post("/models/pull", json={"name": "some-model"})
        assert response.status_code == 501
        body = response.json()
        assert body["error"] == "not_implemented"
        assert "LM Studio" in body["message"]


@pytest.mark.anyio
async def test_delete_model_lmstudio_fallback(client):
    """Wenn der Provider LM Studio ist (keine 11434 im Port), wird ein 501 zurückgegeben."""
    fake_client = FakeClient("http://127.0.0.1:1234/v1")
    
    with patch("backend.routers.models_router._make_alive_client", AsyncMock(return_value=(fake_client, True, False))):
        response = client.delete("/models/some-model")
        assert response.status_code == 501
        body = response.json()
        assert body["error"] == "not_implemented"
        assert "LM Studio" in body["message"]


@pytest.mark.anyio
async def test_delete_model_ollama_forwarding(client):
    """Wenn der Provider Ollama ist (Port 11434), wird die Anfrage direkt an Ollamas DELETE-API gesendet."""
    fake_client = FakeClient("http://localhost:11434/v1")
    
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = "OK"
    
    with patch("backend.routers.models_router._make_alive_client", AsyncMock(return_value=(fake_client, False, True))):
        with patch("httpx.AsyncClient.request", AsyncMock(return_value=mock_resp)) as mock_request:
            response = client.delete("/models/my-ollama-model")
            assert response.status_code == 200
            assert response.json()["status"] == "success"
            
            # Überprüfe, ob der HTTP-Request an Ollama korrekt formatiert war
            mock_request.assert_called_once_with(
                "DELETE",
                "http://localhost:11434/api/delete",
                json={"name": "my-ollama-model"}
            )


@pytest.mark.anyio
async def test_pull_model_ollama_forwarding(client):
    """Wenn der Provider Ollama ist (Port 11434), wird die Anfrage direkt an Ollamas PULL-API weitergeleitet."""
    fake_client = FakeClient("http://localhost:11434/v1")
    
    # Mock den HTTPX Stream-Aufruf
    mock_stream_ctx = MagicMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    
    async def fake_aiter_lines():
        yield '{"status": "pulling layer 1", "completed": 50, "total": 100}'
        yield '{"status": "success"}'
        
    mock_response.aiter_lines = fake_aiter_lines
    mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_response)
    mock_stream_ctx.__aexit__ = AsyncMock()
    
    with patch("backend.routers.models_router._make_alive_client", AsyncMock(return_value=(fake_client, False, True))):
        with patch("httpx.AsyncClient.stream", return_value=mock_stream_ctx) as mock_stream:
            response = client.post("/models/pull", json={"name": "my-ollama-model"})
            assert response.status_code == 200
            assert "text/event-stream" in response.headers["content-type"]
            
            # Lies die Streaming-Events aus der Antwort
            lines = [line if isinstance(line, str) else line.decode("utf-8") for line in response.iter_lines()]
            non_empty_lines = [l for l in lines if l.strip()]
            
            # Erwarte zwei pull_progress Events
            assert len(non_empty_lines) == 4  # event: ... \n data: ... mal 2
            assert "event: pull_progress" in non_empty_lines[0]
            assert "pulling layer 1" in non_empty_lines[1]
            assert "event: pull_progress" in non_empty_lines[2]
            assert "success" in non_empty_lines[3]
            
            mock_stream.assert_called_once_with(
                "POST",
                "http://localhost:11434/api/pull",
                json={"name": "my-ollama-model", "stream": True}
            )
