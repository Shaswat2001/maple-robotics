import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, Optional, List
from enum import Enum

from maple.utils.logging import get_logger

log = get_logger("health")


class HealthStatus(Enum):
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"
    RESTARTING = "restarting"

@dataclass
class MonitoredContainer:

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
    
    def to_dict(self) -> dict:
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

    def __init__(self, 
                 check_interval: float = 30.0, 
                 on_unhealthy: Optional[Callable[[MonitoredContainer], None]] = None):
        
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
    ):
        """
        Register a container for health monitoring.
        
        Args:
            container_id: Docker container ID
            name: Human-readable name
            check_fn: Function that returns True if healthy
            restart_fn: Function to restart container (optional)
            auto_restart: Whether to auto-restart on failure
            max_failures: Consecutive failures before marking unhealthy
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

    def unregister(self, container_id: str):

        with self._lock:
            if container_id in self._containers:
                name = self._containers[container_id].name
                del self._containers[container_id]
                log.debug(f"Unregistered container from monitoring: {name}")
    
    def start(self):

        if self._running:
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        log.info(f"Health monitor started (interval={self.check_interval}s)")

    def stop(self):

        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None
        log.info("Health monitor stopped")
    
    def _monitor_loop(self):
        """Main monitoring loop."""
        while self._running:
            with self._lock:
                containers = list(self._containers.values())
            
            for container in containers:
                self._check_container(container)
            
            time.sleep(self.check_interval)
    
    def _check_container(self, container: MonitoredContainer):
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
    
    def _handle_unhealthy(self, container: MonitoredContainer):
        """Handle unhealthy container."""
        if container.status == HealthStatus.RESTARTING:
            return  # Already handling
        
        container.status = HealthStatus.UNHEALTHY
        log.error(f"Container {container.name} is unhealthy")
        
        # Callback
        if self.on_unhealthy:
            try:
                self.on_unhealthy(container)
            except Exception as e:
                log.error(f"on_unhealthy callback failed: {e}")
        
        # Auto-restart
        if container.auto_restart and container.restart_fn:
            self._restart_container(container)
    
    def _restart_container(self, container: MonitoredContainer):
        """Attempt to restart a container."""
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
    
    def get_status(self, container_id: str) -> Optional[dict]:
        """Get status of a monitored container."""
        with self._lock:
            if container_id in self._containers:
                return self._containers[container_id].to_dict()
        return None
    
    def get_all_status(self) -> List[dict]:
        """Get status of all monitored containers."""
        with self._lock:
            return [c.to_dict() for c in self._containers.values()]
    
    def check_now(self, container_id: str) -> Optional[HealthStatus]:
        """Manually trigger a health check."""
        with self._lock:
            if container_id not in self._containers:
                return None
            container = self._containers[container_id]
        
        self._check_container(container)
        return container.status
    
    @property
    def is_running(self) -> bool:
        return self._running
    
    def __len__(self) -> int:
        return len(self._containers)
