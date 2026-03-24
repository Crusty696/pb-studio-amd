import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
from backend.main import app

@pytest.fixture
def client():
    """Returns a TestClient for the FastAPI app."""
    return TestClient(app)

class TestHealthCheck:
    def test_health_check_success(self, client):
        """
        Tests the /health endpoint for a successful response.
        Mocks _check_gpu_available to return True.
        """
        with patch("backend.main._check_gpu_available", return_value=True):
            response = client.get("/health")

            assert response.status_code == 200
            data = response.json()

            assert data["status"] == "ok"
            assert "uptime_seconds" in data
            assert isinstance(data["uptime_seconds"], (int, float))
            assert data["gpu_available"] is True

    def test_health_check_gpu_unavailable(self, client):
        """
        Tests the /health endpoint when the GPU is reported as unavailable.
        Mocks _check_gpu_available to return False.
        """
        with patch("backend.main._check_gpu_available", return_value=False):
            response = client.get("/health")

            assert response.status_code == 200
            data = response.json()

            assert data["status"] == "ok"
            assert data["gpu_available"] is False

    def test_gpu_status_endpoint_success(self, client):
        """
        Tests the /gpu/status endpoint for a successful response.
        Mocks the SystemMonitor to return sample GPU stats.
        """
        mock_stats = {
            "gpu_name": "AMD Radeon RX 7800 XT",
            "gpu_memory_total": 16384,
            "gpu_memory_used": 4096,
            "gpu_temp": 55,
            "driver_version": "24.1.1",
        }

        with patch("pb_studio.core.system_monitor.SystemMonitor") as MockMonitor:
            instance = MockMonitor.return_value
            instance.get_stats.return_value = mock_stats

            response = client.get("/gpu/status")

            assert response.status_code == 200
            data = response.json()
            assert data["name"] == "AMD Radeon RX 7800 XT"
            assert data["vram_total_mb"] == 16384
            assert data["vram_used_mb"] == 4096
            assert data["temperature_c"] == 55
            assert data["driver_version"] == "24.1.1"

    def test_gpu_status_endpoint_failure(self, client):
        """
        Tests the /gpu/status endpoint when an error occurs during monitoring.
        Verify fallback response.
        """
        with patch("pb_studio.core.system_monitor.SystemMonitor", side_effect=Exception("Monitor failed")):
            response = client.get("/gpu/status")

            assert response.status_code == 200
            data = response.json()
            assert data["name"] == "Nicht verfügbar"
            assert data["vram_total_mb"] == 0
            assert "Monitor failed" in data["driver_version"]
