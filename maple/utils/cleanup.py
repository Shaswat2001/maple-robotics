import atexit
import signal
import sys
import threading
from typing import Callable, Dict, Optional, Set

from maple.utils.logging import get_logger

log = get_logger("cleanup")

class CleanupManager:

    _instance: Optional["CleanupManager"] = None
    _lock = threading.Lock()

    def __init__(self):
        self._containers: Set[str] = set()
        self._cleanup_handlers: Dict[str, Callable] = {}
        self._docker_client = None
        self._signals_registered = None
        self._shutting_down = False

    @classmethod
    def instance(cls) -> "CleanupManager":

        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
                    cls._instance._register_handlers()
        return cls._instance
    
    def _get_docker_client(self):

        if self._docker_client is None:
            try:
                import docker
                self._docker_client = docker.from_env()
            except Exception as e:
                log.warning(f"Could not create Docker client: {e}")
        return self._docker_client
    
    def _register_handlers(self):
        
        if self._signals_registered:
            return
        
        atexit.register(self.cleanup_all) # Normal exit

        self._original_sigint = signal.getsignal(signal.SIGINT)
        self._original_sigterm = signal.getsignal(signal.SIGTERM)

        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        self._signals_registered = True
        log.debug("Cleanup handlers registered")

    def _signal_handler(self, signum, frame):
        sig_name = signal.Signals(signum).name
        log.info(f"Received {sig_name}, cleaning up...")
        
        self.cleanup_all()
        
        # Call original handler or exit
        if signum == signal.SIGINT and callable(self._original_sigint):
            self._original_sigint(signum, frame)
        elif signum == signal.SIGTERM and callable(self._original_sigterm):
            self._original_sigterm(signum, frame)
        else:
            sys.exit(128 + signum)

    def register_container(self, container_id: str, name: str = None):
        self._containers.add(container_id)
        log.debug(f"Registered container for cleanup: {name or container_id[:12]}")
    
    def unregister_container(self, container_id: str):
        self._containers.discard(container_id)
        log.debug(f"Unregistered container: {container_id[:12]}")
    
    def register_handler(self, name: str, handler: Callable):
        self._cleanup_handlers[name] = handler
        log.debug(f"Registered cleanup handler: {name}")
    
    def unregister_handler(self, name: str):
        """Unregister a custom cleanup handler."""
        self._cleanup_handlers.pop(name, None)
    
    def cleanup_all(self):
        if self._shutting_down:
            return
        
        self._shutting_down = True
        
        # Stop containers
        if self._containers:
            log.info(f"Cleaning up {len(self._containers)} container(s)...")
            client = self._get_docker_client()
            
            if client:
                for cid in list(self._containers):
                    self._stop_container(client, cid)
            
            self._containers.clear()
        
        # Run custom handlers
        for name, handler in list(self._cleanup_handlers.items()):
            try:
                log.debug(f"Running cleanup handler: {name}")
                handler()
            except Exception as e:
                log.warning(f"Cleanup handler '{name}' failed: {e}")
        
        self._cleanup_handlers.clear()
        self._shutting_down = False
    
    def _stop_container(self, client, container_id: str):
        """Stop and remove a single container."""
        try:
            container = client.containers.get(container_id)
            name = container.name
            
            log.debug(f"Stopping container: {name} ({container_id[:12]})")
            container.stop(timeout=10)
            
            log.debug(f"Removing container: {name}")
            container.remove(force=True)
            
            log.info(f"Cleaned up container: {name}")
            
        except Exception as e:
            # Container might already be stopped/removed
            log.debug(f"Could not cleanup container {container_id[:12]}: {e}")
    
    @property
    def active_containers(self) -> Set[str]:
        """Get set of currently registered container IDs."""
        return self._containers.copy()
    
    def __len__(self) -> int:
        """Number of registered containers."""
        return len(self._containers)

# Convenience functions using global instance

def register_container(container_id: str, name: str = None):
    """Register a container for automatic cleanup."""
    CleanupManager.instance().register_container(container_id, name)


def unregister_container(container_id: str):
    """Unregister a container from automatic cleanup."""
    CleanupManager.instance().unregister_container(container_id)


def register_cleanup_handler(name: str, handler: Callable):
    """Register a custom cleanup handler."""
    CleanupManager.instance().register_handler(name, handler)


def cleanup_all():
    """Manually trigger cleanup of all resources."""
    CleanupManager.instance().cleanup_all()
