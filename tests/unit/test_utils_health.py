"""
Unit tests for maple.utils.health module.

Tests cover:
- HealthMonitor container registration/unregistration
- Health check execution and status tracking
- Failure threshold and unhealthy callbacks
- MonitoredContainer data class
"""

import pytest
import time
from unittest.mock import MagicMock


class TestHealthStatus:
    """Tests for HealthStatus enum."""
    
    @pytest.mark.unit
    def test_health_status_values(self):
        """Test HealthStatus enum has expected values."""
        from maple.utils.health import HealthStatus
        
        assert HealthStatus.HEALTHY.value == "healthy"
        assert HealthStatus.UNHEALTHY.value == "unhealthy"
        assert HealthStatus.UNKNOWN.value == "unknown"
        assert HealthStatus.RESTARTING.value == "restarting"


class TestMonitoredContainer:
    """Tests for MonitoredContainer data class."""
    
    @pytest.mark.unit
    def test_to_dict(self):
        """Test MonitoredContainer serialization."""
        from maple.utils.health import MonitoredContainer, HealthStatus
        
        container = MonitoredContainer(
            container_id="test123",
            name="test-container",
            check_fn=lambda: True,
        )
        
        d = container.to_dict()
        
        assert d["container_id"] == "test123"
        assert d["name"] == "test-container"
        assert d["status"] == "unknown"
        assert d["consecutive_failures"] == 0
    
    @pytest.mark.unit
    def test_default_values(self):
        """Test MonitoredContainer defaults."""
        from maple.utils.health import MonitoredContainer, HealthStatus
        
        container = MonitoredContainer(
            container_id="test",
            name="test",
            check_fn=lambda: True,
        )
        
        assert container.status == HealthStatus.UNKNOWN
        assert container.consecutive_failures == 0
        assert container.auto_restart is False
        assert container.max_failures == 3


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
        """Test unregistering a container from monitoring."""
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
        """Test getting container health status."""
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
        """Test that successful health check marks container healthy."""
        from maple.utils.health import HealthMonitor, HealthStatus
        
        monitor = HealthMonitor(check_interval=0.1)
        
        check_fn = MagicMock(return_value=True)
        monitor.register("healthy_test", "test", check_fn)
        
        # Get the container and manually run check
        container = monitor._containers["healthy_test"]
        monitor._check_container(container)
        
        assert container.status == HealthStatus.HEALTHY
        assert container.consecutive_failures == 0
    
    @pytest.mark.unit
    def test_health_check_failure_counting(self):
        """Test that failed health checks increment failure count."""
        from maple.utils.health import HealthMonitor, HealthStatus
        
        monitor = HealthMonitor(check_interval=0.1)
        
        check_fn = MagicMock(return_value=False)
        monitor.register(
            container_id="unhealthy_test",
            name="test",
            check_fn=check_fn,
            max_failures=2,
        )
        
        container = monitor._containers["unhealthy_test"]
        
        # First failure
        monitor._check_container(container)
        assert container.consecutive_failures == 1
        assert container.status == HealthStatus.UNKNOWN  # Not yet unhealthy
        
        # Second failure - now unhealthy
        monitor._check_container(container)
        assert container.consecutive_failures == 2
        assert container.status == HealthStatus.UNHEALTHY
    
    @pytest.mark.unit
    def test_on_unhealthy_callback(self):
        """Test that unhealthy callback is invoked."""
        from maple.utils.health import HealthMonitor
        
        callback = MagicMock()
        monitor = HealthMonitor(check_interval=0.1, on_unhealthy=callback)
        
        monitor.register(
            container_id="callback_test",
            name="test",
            check_fn=lambda: False,
            max_failures=1,
        )
        
        container = monitor._containers["callback_test"]
        monitor._check_container(container)
        
        callback.assert_called_once()
        # Callback should receive the container object
        call_args = callback.call_args[0]
        assert call_args[0].container_id == "callback_test"
    
    @pytest.mark.unit
    def test_is_running_property(self):
        """Test is_running property."""
        from maple.utils.health import HealthMonitor
        
        monitor = HealthMonitor(check_interval=1.0)
        
        assert monitor.is_running is False
        
        # Don't actually start the thread in unit test
        monitor._running = True
        assert monitor.is_running is True