"""
Integration tests for Maple daemon server.

These tests verify the VLADaemon class and its FastAPI endpoints work correctly.
Run with: pytest tests/integration/test_daemon.py -m integration
"""

import pytest
from unittest.mock import MagicMock, patch


@pytest.mark.integration
class TestVLADaemon:
    """Tests for VLADaemon class."""
    
    def test_daemon_imports(self):
        """Test daemon module is importable."""
        from maple.server.daemon import VLADaemon
        
        assert VLADaemon is not None
    
    def test_daemon_has_required_classes(self):
        """Test daemon module has required request models."""
        from maple.server import daemon
        
        assert hasattr(daemon, "RunRequest")
        assert hasattr(daemon, "ServePolicyRequest")
        assert hasattr(daemon, "ServeEnvRequest")
        assert hasattr(daemon, "ActRequest")
        assert hasattr(daemon, "SetupEnvRequest")
        assert hasattr(daemon, "StepEnvRequest")


@pytest.mark.integration
class TestDaemonInitialization:
    """Tests for daemon initialization."""
    
    def test_daemon_creates_fastapi_app(self, mock_docker_client):
        """Test daemon creates FastAPI app on init."""
        with patch("maple.state.store.clear_containers"):
            with patch("maple.utils.cleanup.register_cleanup_handler"):
                from maple.server.daemon import VLADaemon
                
                daemon = VLADaemon(port=8000, device="cpu")
                
                # Daemon should have app attribute
                assert hasattr(daemon, "app")
                assert daemon.port == 8000
                assert daemon.device == "cpu"
    
    def test_daemon_app_has_routes(self, mock_docker_client):
        """Test daemon app has expected routes."""
        with patch("maple.state.store.clear_containers"):
            with patch("maple.utils.cleanup.register_cleanup_handler"):
                from maple.server.daemon import VLADaemon
                
                daemon = VLADaemon(port=8000, device="cpu")
                
                # Get route paths
                routes = [route.path for route in daemon.app.routes]
                
                # Should have status endpoint
                assert "/status" in routes


@pytest.mark.integration
class TestDaemonEndpoints:
    """Tests for daemon endpoint definitions."""
    
    def test_status_endpoint_defined(self, mock_docker_client):
        """Test status endpoint is defined."""
        with patch("maple.state.store.clear_containers"):
            with patch("maple.utils.cleanup.register_cleanup_handler"):
                from maple.server.daemon import VLADaemon
                
                daemon = VLADaemon(port=8000, device="cpu")
                routes = [route.path for route in daemon.app.routes]
                
                assert "/status" in routes
    
    def test_run_endpoint_defined(self, mock_docker_client):
        """Test run endpoint is defined."""
        with patch("maple.state.store.clear_containers"):
            with patch("maple.utils.cleanup.register_cleanup_handler"):
                from maple.server.daemon import VLADaemon
                
                daemon = VLADaemon(port=8000, device="cpu")
                routes = [route.path for route in daemon.app.routes]
                
                assert "/run" in routes
    
    def test_stop_endpoint_defined(self, mock_docker_client):
        """Test stop endpoint is defined."""
        with patch("maple.state.store.clear_containers"):
            with patch("maple.utils.cleanup.register_cleanup_handler"):
                from maple.server.daemon import VLADaemon
                
                daemon = VLADaemon(port=8000, device="cpu")
                routes = [route.path for route in daemon.app.routes]
                
                assert "/stop" in routes


@pytest.mark.integration
class TestRequestModels:
    """Tests for request model validation."""
    
    def test_run_request_model(self):
        """Test RunRequest model fields."""
        from maple.server.daemon import RunRequest
        
        req = RunRequest(
            policy_id="test-policy",
            env_id="test-env",
            task="test-task"
        )
        
        assert req.policy_id == "test-policy"
        assert req.env_id == "test-env"
        assert req.task == "test-task"
        assert req.max_steps == 300  # default
    
    def test_serve_policy_request_model(self):
        """Test ServePolicyRequest model fields."""
        from maple.server.daemon import ServePolicyRequest
        
        req = ServePolicyRequest(spec="openvla:7b")
        
        assert req.spec == "openvla:7b"
        assert req.device == "cpu"  # default
    
    def test_act_request_model(self):
        """Test ActRequest model fields."""
        from maple.server.daemon import ActRequest
        
        req = ActRequest(
            policy_id="test-policy",
            image="base64_image_data",
            instruction="pick up the block"
        )
        
        assert req.policy_id == "test-policy"
        assert req.image == "base64_image_data"
        assert req.instruction == "pick up the block"
