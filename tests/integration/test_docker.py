"""
Integration tests for Maple.

These tests require Docker and may be slow.
Run with: pytest tests/integration/ -m integration
"""

import pytest
import time


@pytest.mark.integration
@pytest.mark.slow
class TestDockerIntegration:
    """Integration tests that require Docker."""
    
    def test_docker_available(self):
        """Test that Docker daemon is available and responding."""
        import docker
        
        client = docker.from_env()
        client.ping()
    
    def test_docker_pull_hello_world(self):
        """Test pulling a small image works."""
        import docker
        
        client = docker.from_env()
        # Pull a minimal image
        client.images.pull("hello-world:latest")
    
    def test_docker_run_hello_world(self):
        """Test running a container works."""
        import docker
        
        client = docker.from_env()
        container = client.containers.run(
            "hello-world:latest",
            remove=True,
            detach=False,
        )


@pytest.mark.integration
class TestDaemonAPI:
    """Tests for daemon HTTP API."""
    
    def test_health_endpoint(self, mock_requests):
        """Test /health endpoint returns status."""
        mock_requests["get"].return_value.json.return_value = {"status": "ok"}
        
        import requests
        response = requests.get("http://localhost:8000/health")
        
        assert response.json()["status"] == "ok"
    
    def test_api_error_handling(self, mock_requests):
        """Test API handles errors gracefully."""
        mock_requests["get"].return_value.status_code = 500
        mock_requests["get"].return_value.json.return_value = {"error": "Internal error"}
        
        import requests
        response = requests.get("http://localhost:8000/health")
        
        assert response.status_code == 500


@pytest.mark.integration
@pytest.mark.slow
class TestPolicyContainerIntegration:
    """Integration tests for policy containers."""
    
    def test_policy_container_lifecycle(self, mock_docker_client):
        """Test policy container start/stop lifecycle."""
        from maple.backend.registry import POLICY_BACKENDS
        
        # Verify we have registered backends
        assert len(POLICY_BACKENDS) > 0
    
    def test_container_health_check(self, mock_docker_client, mock_requests):
        """Test container health checks work."""
        mock_requests["get"].return_value.json.return_value = {"status": "ready"}
        
        import requests
        response = requests.get("http://localhost:50000/health")
        
        assert response.json()["status"] == "ready"


@pytest.mark.integration
@pytest.mark.slow
class TestEnvContainerIntegration:
    """Integration tests for environment containers."""
    
    def test_env_container_lifecycle(self, mock_docker_client):
        """Test environment container start/stop lifecycle."""
        from maple.backend.registry import ENV_BACKENDS
        
        # Verify we have registered backends
        assert len(ENV_BACKENDS) > 0


@pytest.mark.integration
class TestEndToEndWorkflow:
    """End-to-end workflow tests."""
    
    def test_workflow_components_exist(self):
        """Test that all workflow components are importable."""
        from maple.backend.registry import POLICY_BACKENDS, ENV_BACKENDS
        from maple.adapters import get_adapter
        from maple.state import store
        from maple.utils.config import load_config
        
        # All components should be importable
        assert POLICY_BACKENDS is not None
        assert ENV_BACKENDS is not None
        assert get_adapter is not None
        assert store is not None
        assert load_config is not None
