"""
Resource cleanup utilities.

This module provides automatic cleanup management for Docker containers and other
resources. It ensures proper cleanup when:
- Program exits normally
- Program crashes
- User presses Ctrl+C (SIGINT)
- SIGTERM is received
"""

import sys
import atexit
import signal
import docker
import threading
from docker.client import DockerClient
from typing import Callable, Dict, Optional, Set

from maple.utils.logging import get_logger

log = get_logger("cleanup")

class CleanupManager:
    """
    Singleton manager for automatic resource cleanup.
    
    Manages cleanup of Docker containers and custom cleanup handlers. Uses
    signal handlers (SIGINT, SIGTERM) and atexit hooks to ensure resources
    are properly cleaned up even when the program terminates unexpectedly.
    
    The class implements thread-safe singleton pattern to ensure only one
    instance exists throughout the application lifecycle.
    """
    
    # Class-level singleton instance and lock for thread safety
    _instance: Optional["CleanupManager"] = None
    _lock = threading.Lock()

    def __init__(self):
        """
        Initialize the CleanupManager instance.
        
        Creates internal data structures for tracking containers and cleanup
        handlers. Should not be called directly - use instance() classmethod.
        """
        # Set of container IDs registered for cleanup
        self._containers: Set[str] = set()
        
        # Dict of named cleanup handlers (name -> callable)
        self._cleanup_handlers: Dict[str, Callable] = {}
        
        # Lazily initialized Docker client
        self._docker_client = None
        
        # Flag to track if signal handlers have been registered
        self._signals_registered = None
        
        # Flag to prevent recursive cleanup calls
        self._shutting_down = False

    @classmethod
    def instance(cls) -> "CleanupManager":
        """
        Get the singleton instance of CleanupManager.
        
        Creates the instance on first call and registers cleanup handlers.
        Thread-safe implementation using double-checked locking pattern.
        
        :return: The singleton CleanupManager instance.
        """
        # First check without lock (fast path)
        if cls._instance is None:
            # Acquire lock for instance creation
            with cls._lock:
                # Double-check after acquiring lock
                if cls._instance is None:
                    cls._instance = cls()
                    # Register signal handlers and atexit hook
                    cls._instance._register_handlers()
        return cls._instance

    def _get_docker_client(self) -> DockerClient:
        """
        Get or create a Docker client instance.
        
        Lazily creates and caches a Docker client. Logs a warning if
        Docker is not available or client creation fails.
        
        :return: Docker client instance, or None if unavailable.
        """
        if self._docker_client is None:
            try:
                # Create Docker client from environment variables
                self._docker_client = docker.from_env()
            except Exception as e:
                # Docker daemon may not be running or accessible
                log.warning(f"Could not create Docker client: {e}")
        return self._docker_client

    def _register_handlers(self) -> None:
        """
        Register signal handlers and atexit callback.
        
        Registers cleanup_all() to be called on:
        - Normal program exit (atexit)
        - SIGINT (Ctrl+C)
        - SIGTERM (termination signal)
        
        Preserves original signal handlers to allow proper cleanup chain.
        Only registers handlers once, even if called multiple times.
        """
        # Skip if already registered
        if self._signals_registered:
            return

        # Register for normal program exit
        atexit.register(self.cleanup_all)

        # Save original signal handlers so we can call them after cleanup
        self._original_sigint = signal.getsignal(signal.SIGINT)
        self._original_sigterm = signal.getsignal(signal.SIGTERM)

        # Register our custom signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        # Mark handlers as registered
        self._signals_registered = True
        log.debug("Cleanup handlers registered")

    def _signal_handler(self, signum, frame) -> None:
        """
        Handle SIGINT and SIGTERM signals.
        
        Performs cleanup and then calls the original signal handler if one
        existed, or exits with appropriate exit code.
        
        :param signum: Signal number (e.g., signal.SIGINT, signal.SIGTERM).
        :param frame: Current stack frame (unused but required by signal API).
        """
        # Convert signal number to human-readable name for logging
        sig_name = signal.Signals(signum).name
        log.info(f"Received {sig_name}, cleaning up...")
        
        # Perform cleanup of all resources
        self.cleanup_all()

        # Call original handler if it was a callable (not SIG_DFL or SIG_IGN)
        if signum == signal.SIGINT and callable(self._original_sigint):
            self._original_sigint(signum, frame)
        elif signum == signal.SIGTERM and callable(self._original_sigterm):
            self._original_sigterm(signum, frame)
        else:
            # Exit with standard Unix signal exit code (128 + signal number)
            sys.exit(128 + signum)

    def register_container(self, container_id: str, name: str = None):
        """
        Register a Docker container for automatic cleanup.
        
        Adds the container to the cleanup registry. The container will be
        stopped and removed when cleanup_all() is called.
        
        :param container_id: Docker container ID to register.
        :param name: Optional human-readable name for logging purposes.
        """
        # Add to set of containers to clean up
        self._containers.add(container_id)
        # Log with name if provided, otherwise show truncated container ID
        log.debug(f"Registered container for cleanup: {name or container_id[:12]}")

    def unregister_container(self, container_id: str) -> None:
        """
        Unregister a Docker container from automatic cleanup.
        
        Removes the container from the cleanup registry. Typically called
        when a container is stopped manually and cleanup is no longer needed.
        
        :param container_id: Docker container ID to unregister.
        """
        # Remove from set (discard doesn't raise if not present)
        self._containers.discard(container_id)
        log.debug(f"Unregistered container: {container_id[:12]}")

    def register_handler(self, name: str, handler: Callable) -> None:
        """
        Register a custom cleanup handler function.
        
        Custom handlers are called during cleanup_all() after containers
        are stopped. Useful for cleaning up non-Docker resources like
        temporary files, locks, or connections.
        
        :param name: Unique identifier for the cleanup handler.
        :param handler: Callable that performs cleanup (takes no arguments).
        """
        # Store handler in dictionary with unique name
        self._cleanup_handlers[name] = handler
        log.debug(f"Registered cleanup handler: {name}")

    def unregister_handler(self, name: str) -> None:
        """
        Unregister a custom cleanup handler.
        
        Removes a previously registered cleanup handler. Safe to call
        even if the handler doesn't exist.
        
        :param name: Identifier of the cleanup handler to remove.
        """
        # Remove handler (pop with default doesn't raise if not present)
        self._cleanup_handlers.pop(name, None)

    def cleanup_all(self) -> None:
        """
        Clean up all registered resources.
        
        Stops and removes all registered Docker containers, then executes
        all registered cleanup handlers. Prevents recursive calls using
        the _shutting_down flag.
        
        Container cleanup:
        1. Stops each container (10 second timeout)
        2. Removes the container (forced)
        3. Logs success or failure
        
        Handler cleanup:
        1. Executes each handler
        2. Catches and logs exceptions without stopping cleanup
        """
        # Prevent recursive calls (e.g., from signal handler)
        if self._shutting_down:
            return
        
        # Set flag to prevent re-entry
        self._shutting_down = True

        # Clean up Docker containers
        if self._containers:
            log.info(f"Cleaning up {len(self._containers)} container(s)...")
            
            # Get Docker client
            client = self._get_docker_client()
            if client:
                # Stop each registered container
                for cid in list(self._containers):  # Copy to allow modification during iteration
                    self._stop_container(client, cid)
            
            # Clear the container registry
            self._containers.clear()

        # Run custom cleanup handlers
        for name, handler in list(self._cleanup_handlers.items()):  # Copy dict items
            try:
                log.debug(f"Running cleanup handler: {name}")
                # Execute the cleanup function
                handler()
            except Exception as e:
                # Log but don't stop cleanup process
                log.warning(f"Cleanup handler '{name}' failed: {e}")
        
        # Clear the handler registry
        self._cleanup_handlers.clear()
        
        # Reset flag to allow manual cleanup_all() calls later
        self._shutting_down = False

    def _stop_container(self, client, container_id: str) -> None:
        """
        Stop and remove a single Docker container.
        
        Gracefully stops the container with a timeout, then removes it.
        Logs all operations and handles cases where the container may
        already be stopped or removed.
        
        :param client: Docker client instance.
        :param container_id: ID of the container to stop and remove.
        """
        try:
            # Get container object from Docker
            container = client.containers.get(container_id)
            name = container.name
            
            # Gracefully stop the container (10 second timeout before force kill)
            log.debug(f"Stopping container: {name} ({container_id[:12]})")
            container.stop(timeout=10)
            
            # Remove the container from Docker (force=True to remove even if running)
            log.debug(f"Removing container: {name}")
            container.remove(force=True)
            
            log.info(f"Cleaned up container: {name}")
        except Exception as e:
            # Container might already be stopped/removed, or Docker daemon unreachable
            # Log at debug level since this is often expected
            log.debug(f"Could not cleanup container {container_id[:12]}: {e}")

    @property
    def active_containers(self) -> Set[str]:
        """
        Get set of currently registered container IDs.
        
        Returns a copy of the internal set to prevent external modification.
        
        :return: Set of Docker container IDs registered for cleanup.
        """
        # Return copy to prevent external modification of internal state
        return self._containers.copy()

    def __len__(self) -> int:
        """
        Get number of registered containers.
        
        :return: Count of containers currently registered for cleanup.
        """
        return len(self._containers)

# Convenience functions using global singleton instance
def register_container(container_id: str, name: str = None) -> None:
    """
    Register a container for automatic cleanup.
    
    Convenience function that uses the global CleanupManager singleton.
    
    :param container_id: Docker container ID to register.
    :param name: Optional human-readable name for logging.
    """
    # Delegate to singleton instance
    CleanupManager.instance().register_container(container_id, name)

def unregister_container(container_id: str) -> None:
    """
    Unregister a container from automatic cleanup.
    
    Convenience function that uses the global CleanupManager singleton.
    
    :param container_id: Docker container ID to unregister.
    """
    # Delegate to singleton instance
    CleanupManager.instance().unregister_container(container_id)

def register_cleanup_handler(name: str, handler: Callable) -> None:
    """
    Register a custom cleanup handler.
    
    Convenience function that uses the global CleanupManager singleton.
    
    :param name: Unique identifier for the cleanup handler.
    :param handler: Callable that performs cleanup (takes no arguments).
    """
    # Delegate to singleton instance
    CleanupManager.instance().register_handler(name, handler)

def cleanup_all() -> None:
    """
    Manually trigger cleanup of all resources.
    
    Convenience function that uses the global CleanupManager singleton.
    Useful for explicit cleanup without waiting for program exit.
    """
    # Delegate to singleton instance
    CleanupManager.instance().cleanup_all()