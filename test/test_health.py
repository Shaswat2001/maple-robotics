"""
Tests for maple.utils.health module.
"""

import pytest
import time
from unittest.mock import MagicMock


class TestHealthMonitor:
    """Tests for HealthMonitor class."""
    
    @pytest.mark.unit
    def test_register_container(self):
        """Test registering a container for monitoring."""
        from maple.utils.health import HealthMonitor
        
        monitor = HealthMonitor(check_interval=1.0)
        
        check_fn = MagicMock(return_value=True)
        monitor.register(
            container_id="test123",
            name="test-container",
            check_fn=check_fn,
            auto_restart=False,
        )
        
        assert "test123" in monitor._containers
        assert monitor._containers["test123"].name == "test-container"
    
    @pytest.mark.unit
    def test_unregister_container(self):
        """Test unregistering a container."""
        from maple.utils.health import HealthMonitor
        
        monitor = HealthMonitor(check_interval=1.0)
        
        monitor.register(
            container_id="to_remove",
            name="temp",
            check_fn=lambda: True,
        )
        
        assert "to_remove" in monitor._containers
        
        monitor.unregister("to_remove")
        
        assert "to_remove" not in monitor._containers
    
    @pytest.mark.unit
    def test_get_status(self):
        """Test getting container status."""
        from maple.utils.health import HealthMonitor, HealthStatus
        
        monitor = HealthMonitor(check_interval=1.0)
        
        monitor.register(
            container_id="status_test",
            name="test",
            check_fn=lambda: True,
        )
        
        status = monitor.get_status("status_test")
        
        assert status is not None
        assert status["name"] == "test"
        assert status["status"] == HealthStatus.UNKNOWN.value
    
    @pytest.mark.unit
    def test_get_all_status(self):
        """Test getting all container statuses."""
        from maple.utils.health import HealthMonitor
        
        monitor = HealthMonitor(check_interval=1.0)
        
        monitor.register("c1", "container1", lambda: True)
        monitor.register("c2", "container2", lambda: True)
        
        all_status = monitor.get_all_status()
        
        assert len(all_status) == 2
        names = [s["name"] for s in all_status]
        assert "container1" in names
        assert "container2" in names
    
    @pytest.mark.unit
    def test_health_check_success(self):
        """Test health check marks container as healthy."""
        from maple.utils.health import HealthMonitor, HealthStatus
        
        monitor = HealthMonitor(check_interval=0.1)
        
        check_fn = MagicMock(return_value=True)
        monitor.register("healthy_test", "test", check_fn)
        
        # Manually run check
        monitor._check_container("healthy_test")
        
        status = monitor.get_status("healthy_test")
        assert status["status"] == HealthStatus.HEALTHY.value
        assert status["consecutive_failures"] == 0
    
    @pytest.mark.unit
    def test_health_check_failure(self):
        """Test health check marks container as unhealthy after failures."""
        from maple.utils.health import HealthMonitor, HealthStatus
        
        monitor = HealthMonitor(check_interval=0.1)
        
        check_fn = MagicMock(return_value=False)
        monitor.register(
            container_id="unhealthy_test",
            name="test",
            check_fn=check_fn,
            max_failures=2,
        )
        
        # First failure
        monitor._check_container("unhealthy_test")
        status = monitor.get_status("unhealthy_test")
        assert status["consecutive_failures"] == 1
        assert status["status"] == HealthStatus.HEALTHY.value  # Not yet unhealthy
        
        # Second failure - now unhealthy
        monitor._check_container("unhealthy_test")
        status = monitor.get_status("unhealthy_test")
        assert status["consecutive_failures"] == 2
        assert status["status"] == HealthStatus.UNHEALTHY.value
    
    @pytest.mark.unit
    def test_on_unhealthy_callback(self):
        """Test unhealthy callback is called."""
        from maple.utils.health import HealthMonitor
        
        callback = MagicMock()
        monitor = HealthMonitor(check_interval=0.1, on_unhealthy=callback)
        
        monitor.register(
            container_id="callback_test",
            name="test",
            check_fn=lambda: False,
            max_failures=1,
        )
        
        monitor._check_container("callback_test")
        
        callback.assert_called_once()
        call_args = callback.call_args[0]
        assert call_args[0] == "callback_test"


class TestDaemonLock:
    """Tests for DaemonLock class."""
    
    @pytest.mark.unit
    def test_acquire_release(self, temp_dir, monkeypatch):
        """Test acquiring and releasing lock."""
        from maple.utils.lock import DaemonLock
        
        socket_path = temp_dir / "test.sock"
        monkeypatch.setattr("maple.utils.lock._get_socket_path", lambda: socket_path)
        
        lock = DaemonLock()
        
        assert lock.acquire() is True
        assert socket_path.exists()
        
        lock.release()
    
    @pytest.mark.unit
    def test_is_daemon_running(self, temp_dir, monkeypatch):
        """Test checking if daemon is running."""
        from maple.utils.lock import DaemonLock, is_daemon_running
        
        socket_path = temp_dir / "test2.sock"
        monkeypatch.setattr("maple.utils.lock._get_socket_path", lambda: socket_path)
        
        # No daemon running
        assert is_daemon_running() is False
        
        # Start daemon
        lock = DaemonLock()
        lock.acquire()
        
        # Now running
        assert is_daemon_running() is True
        
        lock.release()
