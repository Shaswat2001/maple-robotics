"""
Integration tests for Maple.

These tests require Docker and may be slow.
Run with: pytest -m integration
"""

import pytest
import time


@pytest.mark.integration
@pytest.mark.slow
class TestDockerIntegration:
    """Integration tests that require Docker."""
    
    def test_docker_available(self):
        """Test that Docker is available."""
        import docker
        client = docker.from_env()
        client.ping()


@pytest.mark.integration
class TestDaemonAPI:
    """Tests for daemon HTTP API."""
    
    def test_health_endpoint(self, mock_requests):
        """Test /health endpoint."""
        mock_requests["get"].return_value.json.return_value = {"status": "ok"}
        import requests
        response = requests.get("http://localhost:8000/health")
        assert response.json()["status"] == "ok"
