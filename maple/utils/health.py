"""
Container health monitoring utilities.

This module provides automatic health monitoring for Docker containers running
policy backends and environments. It implements a background thread that 
periodically checks container health and can automatically restart failed
containers.

Key features:
- Periodic health checks with configurable intervals
- Automatic restart on failure (optional)
- Consecutive failure counting before marking unhealthy
- Custom health check and restart callbacks
- Thread-safe container registration
- Real-time status reporting

The HealthMonitor class runs a daemon thread that continuously monitors
registered containers and maintains their health status.
"""

import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, Optional, List
from enum import Enum

from maple.utils.logging import get_logger

log = get_logger("health")


class HealthStatus(Enum):
    """
    Health status enumeration for monitored containers.
    
    Represents the current health state of a container being monitored
    by the HealthMonitor.
    """
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"
    RESTARTING = "restarting"


@dataclass
class MonitoredContainer:
    """
    Data class representing a container under health monitoring.
    
    Stores configuration and runtime state for a monitored container,
    including health check callbacks, restart configuration, and
    failure tracking.
    """

    container_id: str
    name: str
    check_fn: Callable[[], bool]
    restart_fn: Optional[Callable[[], None]] = None
    auto_restart: bool = False
    max_failures: int = 3

    status: HealthStatus = HealthStatus.UNKNOWN
    consecutive_failures: int = 0
    last_check: float = 0
    last_healthy: float = 0
    total_restarts: int = 0
    
    def to_dict(self) -> Dict:
        """
        Convert container state to dictionary format.
        
        Serializes the container's current state for status reporting
        and API responses. Excludes callable fields.
        
        return: Dictionary containing container status information.
        """
        return {
            "container_id": self.container_id,
            "name": self.name,
            "status": self.status.value,
            "consecutive_failures": self.consecutive_failures,
            "last_check": self.last_check,
            "last_healthy": self.last_healthy,
            "total_restarts": self.total_restarts,
            "auto_restart": self.auto_restart,
        }


class HealthMonitor:
    """
    Thread-safe health monitor for Docker containers.
    
    Runs a background daemon thread that periodically checks the health
    of registered containers. Supports automatic restart on failure,
    custom health check callbacks, and real-time status reporting.
    
    The monitor runs continuously once started and checks all registered
    containers at the specified interval. Containers are marked unhealthy
    after a configurable number of consecutive failures.
    
    Thread-safety: All public methods are thread-safe and can be called
    from multiple threads concurrently.
    """

    def __init__(self, 
                 check_interval: float = 30.0, 
                 on_unhealthy: Optional[Callable[[MonitoredContainer], None]] = None):
        """
        Initialize the HealthMonitor.
        
        Creates the monitor with specified check interval and optional
        unhealthy callback. The monitor must be started explicitly with
        start() to begin monitoring.
        
        param: check_interval: Seconds between health checks for all containers.
        param: on_unhealthy: Optional callback invoked when a container becomes
                            unhealthy. Receives MonitoredContainer as argument.
        """
        self.check_interval = check_interval
        self.on_unhealthy = on_unhealthy

        self._containers: Dict[str, MonitoredContainer] = {}
        self._lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def register(
        self,
        container_id: str,
        name: str,
        check_fn: Callable[[], bool],
        restart_fn: Optional[Callable[[], None]] = None,
        auto_restart: bool = False,
        max_failures: int = 3,
    ) -> None:
        """
        Register a container for health monitoring.
        
        Adds a container to the monitoring registry. The container will be
        checked periodically according to check_interval once the monitor
        is started. Thread-safe and can be called while monitor is running.
        
        param: container_id: Docker container ID to monitor.
        param: name: Policy/Env instance name for logging and status reports.
        param: check_fn: Callable that returns True if container is healthy,
                        False otherwise. Should not raise exceptions.
        param: restart_fn: Optional callable to restart the container when
                          unhealthy. Only used if auto_restart is True.
        param: auto_restart: If True, automatically call restart_fn when
                            container becomes unhealthy.
        param: max_failures: Number of consecutive health check failures
                            before marking container as unhealthy.
        """
        with self._lock:
            self._containers[container_id] = MonitoredContainer(
                container_id=container_id,
                name=name,
                check_fn=check_fn,
                restart_fn=restart_fn,
                auto_restart=auto_restart,
                max_failures=max_failures,
                last_check=time.time(),
            )
        log.debug(f"Registered container for monitoring: {name}")

    def unregister(self, container_id: str) -> None:
        """
        Unregister a container from health monitoring.
        
        Removes the container from the monitoring registry. The container
        will no longer be checked. Thread-safe and can be called while
        monitor is running. Safe to call even if container is not registered.
        
        param: container_id: Docker container ID to unregister.
        """
        with self._lock:
            if container_id in self._containers:
                name = self._containers[container_id].name
                del self._containers[container_id]
                log.debug(f"Unregistered container from monitoring: {name}")
    
    def start(self) -> None:
        """
        Start the health monitoring background thread.
        
        Launches a daemon thread that continuously monitors all registered
        containers at the configured check_interval. Safe to call multiple
        times - will not start duplicate threads.
        
        The monitoring thread will automatically exit when the program
        terminates since it runs as a daemon.
        """
        if self._running:
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        log.info(f"Health monitor started (interval={self.check_interval}s)")

    def stop(self) -> None:
        """
        Stop the health monitoring background thread.
        
        Gracefully shuts down the monitoring thread. Waits up to 5 seconds
        for the thread to exit. Safe to call multiple times or if monitor
        is not running.
        """
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None
        log.info("Health monitor stopped")
    
    def _monitor_loop(self):
        """
        Main monitoring loop running in background thread.
        
        Continuously checks all registered containers at the configured
        interval. Runs until stop() is called. Thread-safe access to
        container registry.
        """
        while self._running:
            with self._lock:
                containers = list(self._containers.values())
            
            for container in containers:
                self._check_container(container)
            
            time.sleep(self.check_interval)
    
    def _check_container(self, container: MonitoredContainer) -> None:
        """
        Perform health check on a single container.
        
        Calls the container's check_fn and updates its status. Tracks
        consecutive failures and triggers unhealthy handling when
        max_failures is reached. Handles exceptions from check_fn
        gracefully.
        
        param: container: MonitoredContainer instance to check.
        """
        try:
            healthy = container.check_fn()
            container.last_check = time.time()

            if healthy:
                if container.status != HealthStatus.HEALTHY:
                    log.info(f"Container {container.name} is now healthy")
                container.status = HealthStatus.HEALTHY
                container.consecutive_failures = 0
                container.last_healthy = time.time()
            else:
                container.consecutive_failures += 1
                log.warning(
                    f"Container {container.name} health check failed "
                    f"({container.consecutive_failures}/{container.max_failures})"
                )
                
                if container.consecutive_failures >= container.max_failures:
                    self._handle_unhealthy(container)
        except Exception as e:
            container.consecutive_failures += 1
            container.last_check = time.time()
            log.warning(f"Health check error for {container.name}: {e}")
            
            if container.consecutive_failures >= container.max_failures:
                self._handle_unhealthy(container)
    
    def _handle_unhealthy(self, container: MonitoredContainer) -> None:
        """
        Handle a container that has become unhealthy.
        
        Marks the container as unhealthy, invokes the on_unhealthy callback
        if configured, and attempts automatic restart if enabled. Prevents
        duplicate restart attempts while restart is in progress.
        
        param: container: MonitoredContainer that has become unhealthy.
        """
        if container.status == HealthStatus.RESTARTING:
            return  # Already handling
        
        container.status = HealthStatus.UNHEALTHY
        log.error(f"Container {container.name} is unhealthy")
        
        # Invoke callback
        if self.on_unhealthy:
            try:
                self.on_unhealthy(container)
            except Exception as e:
                log.error(f"on_unhealthy callback failed: {e}")
        
        # Attempt auto-restart
        if container.auto_restart and container.restart_fn:
            self._restart_container(container)
    
    def _restart_container(self, container: MonitoredContainer) -> None:
        """
        Attempt to restart an unhealthy container.
        
        Calls the container's restart_fn and updates status accordingly.
        Resets failure counter on successful restart. Handles exceptions
        from restart_fn and marks container unhealthy if restart fails.
        
        param: container: MonitoredContainer to restart.
        """
        container.status = HealthStatus.RESTARTING
        log.info(f"Attempting to restart container {container.name}...")
        
        try:
            container.restart_fn()
            container.total_restarts += 1
            container.consecutive_failures = 0
            container.status = HealthStatus.HEALTHY
            log.info(f"Container {container.name} restarted successfully")
        except Exception as e:
            log.error(f"Failed to restart container {container.name}: {e}")
            container.status = HealthStatus.UNHEALTHY
    
    def get_status(self, container_id: str) -> Optional[Dict]:
        """
        Get current status of a specific monitored container.
        
        Returns a dictionary with the container's current health status,
        failure counts, and timing information. Thread-safe.
        
        param: container_id: Docker container ID to query.
        return: Dictionary containing container status, or None if container
                is not registered.
        """
        with self._lock:
            if container_id in self._containers:
                return self._containers[container_id].to_dict()
        return None
    
    def get_all_status(self) -> List[Dict]:
        """
        Get status of all monitored containers.
        
        Returns a list of status dictionaries for all registered containers.
        Useful for dashboard and monitoring endpoints. Thread-safe.
        
        return: List of dictionaries, each containing a container's status.
        """
        with self._lock:
            return [c.to_dict() for c in self._containers.values()]
    
    def check_now(self, container_id: str) -> Optional[HealthStatus]:
        """
        Manually trigger an immediate health check for a container.
        
        Performs a health check outside the normal monitoring interval.
        Useful for on-demand status verification or testing. Updates
        the container's status based on the check result.
        
        param: container_id: Docker container ID to check.
        return: Updated HealthStatus after the check, or None if container
                is not registered.
        """
        with self._lock:
            if container_id not in self._containers:
                return None
            container = self._containers[container_id]
        
        self._check_container(container)
        return container.status
    
    @property
    def is_running(self) -> bool:
        """
        Check if the health monitor is currently running.
        
        return: True if monitoring thread is active, False otherwise.
        """
        return self._running
    
    def __len__(self) -> int:
        """
        Get number of containers currently being monitored.
        
        return: Count of registered containers.
        """
        return len(self._containers)