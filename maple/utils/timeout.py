"""
Timeout utilities for MAPLE operations.

This module provides timeout handling for policy inference and environment
operations. It wraps operations with configurable timeouts and provides
graceful failure handling.

Key features:
- Configurable timeouts for different operation types
- Thread-based timeout implementation (cross-platform)
- Graceful error messages for timeout failures
- Context manager for timeout blocks
"""

import signal
import threading
import functools
from typing import Callable, Any, Optional, TypeVar, Generic
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

from maple.utils.logging import get_logger

log = get_logger("timeout")

T = TypeVar('T')


class TimeoutError(Exception):
    """Raised when an operation times out."""
    
    def __init__(self, operation: str, timeout: float, message: Optional[str] = None):
        self.operation = operation
        self.timeout = timeout
        if message:
            super().__init__(message)
        else:
            super().__init__(f"{operation} timed out after {timeout:.1f}s")


@dataclass
class TimeoutConfig:
    """Configuration for operation timeouts."""
    
    # Policy inference timeout (per step)
    policy_act: float = 60.0
    
    # Environment operation timeouts
    env_setup: float = 30.0
    env_reset: float = 30.0
    env_step: float = 10.0
    
    # Container health check timeout
    health_check: float = 10.0
    
    # Full episode timeout multiplier (timeout = max_steps * multiplier)
    episode_multiplier: float = 2.0


# Global default config
DEFAULT_TIMEOUT_CONFIG = TimeoutConfig()


def with_timeout(timeout: float, operation: str = "Operation"):
    """
    Decorator to add timeout to a function.
    
    Uses ThreadPoolExecutor for cross-platform timeout support.
    
    :param timeout: Timeout in seconds
    :param operation: Name of operation for error messages
    :return: Decorated function
    
    Example:
        @with_timeout(30.0, "Policy inference")
        def get_action(obs):
            return model.predict(obs)
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(func, *args, **kwargs)
                try:
                    return future.result(timeout=timeout)
                except FuturesTimeoutError:
                    log.error(f"{operation} timed out after {timeout}s")
                    raise TimeoutError(operation, timeout)
        return wrapper
    return decorator


class TimeoutContext:
    """
    Context manager for timeout blocks.
    
    Uses threading for cross-platform support instead of signals.
    
    Example:
        with TimeoutContext(30.0, "Policy inference"):
            action = policy.act(obs)
    """
    
    def __init__(self, timeout: float, operation: str = "Operation"):
        """
        Initialize timeout context.
        
        :param timeout: Timeout in seconds
        :param operation: Name of operation for error messages
        """
        self.timeout = timeout
        self.operation = operation
        self._timer: Optional[threading.Timer] = None
        self._timed_out = False
        self._thread_id: Optional[int] = None
    
    def __enter__(self):
        self._thread_id = threading.current_thread().ident
        self._timed_out = False
        
        def timeout_handler():
            self._timed_out = True
            log.error(f"{self.operation} timed out after {self.timeout}s")
        
        self._timer = threading.Timer(self.timeout, timeout_handler)
        self._timer.daemon = True
        self._timer.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._timer:
            self._timer.cancel()
        
        if self._timed_out and exc_type is None:
            raise TimeoutError(self.operation, self.timeout)
        
        return False
    
    @property
    def is_timed_out(self) -> bool:
        """Check if timeout has been triggered."""
        return self._timed_out


def run_with_timeout(
    func: Callable[[], T],
    timeout: float,
    operation: str = "Operation",
    default: Optional[T] = None,
    raise_on_timeout: bool = True
) -> T:
    """
    Run a function with a timeout.
    
    :param func: Callable to execute
    :param timeout: Timeout in seconds
    :param operation: Name of operation for error messages
    :param default: Default value to return on timeout (if raise_on_timeout=False)
    :param raise_on_timeout: If True, raise TimeoutError on timeout
    :return: Result of func or default on timeout
    
    Example:
        action = run_with_timeout(
            lambda: policy.act(obs),
            timeout=30.0,
            operation="Policy inference"
        )
    """
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(func)
        try:
            return future.result(timeout=timeout)
        except FuturesTimeoutError:
            log.error(f"{operation} timed out after {timeout}s")
            if raise_on_timeout:
                raise TimeoutError(operation, timeout)
            return default


class OperationTimer:
    """
    Timer for tracking operation duration and detecting slow operations.
    
    Logs warnings when operations exceed expected duration.
    
    Example:
        timer = OperationTimer("Policy inference", expected=1.0, warn_threshold=2.0)
        with timer:
            action = policy.act(obs)
        print(f"Took {timer.elapsed:.2f}s")
    """
    
    def __init__(
        self,
        operation: str,
        expected: float = 1.0,
        warn_threshold: float = 2.0,
        log_always: bool = False
    ):
        """
        Initialize operation timer.
        
        :param operation: Name of operation
        :param expected: Expected duration in seconds
        :param warn_threshold: Multiplier for warning (warn if elapsed > expected * threshold)
        :param log_always: If True, always log duration
        """
        self.operation = operation
        self.expected = expected
        self.warn_threshold = warn_threshold
        self.log_always = log_always
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
    
    def __enter__(self):
        import time
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        import time
        self.end_time = time.time()
        
        if self.elapsed > self.expected * self.warn_threshold:
            log.warning(
                f"{self.operation} took {self.elapsed:.2f}s "
                f"(expected ~{self.expected:.2f}s)"
            )
        elif self.log_always:
            log.debug(f"{self.operation} completed in {self.elapsed:.2f}s")
        
        return False
    
    @property
    def elapsed(self) -> float:
        """Get elapsed time in seconds."""
        if self.start_time is None:
            return 0.0
        end = self.end_time if self.end_time else __import__('time').time()
        return end - self.start_time


def check_container_responsive(
    check_fn: Callable[[], bool],
    timeout: float = 10.0,
    container_name: str = "Container"
) -> bool:
    """
    Check if a container is responsive within timeout.
    
    :param check_fn: Function that returns True if container is responsive
    :param timeout: Timeout in seconds
    :param container_name: Name for error messages
    :return: True if responsive, False if timeout or check failed
    """
    try:
        result = run_with_timeout(
            check_fn,
            timeout=timeout,
            operation=f"{container_name} health check",
            raise_on_timeout=False,
            default=False
        )
        return bool(result)
    except Exception as e:
        log.warning(f"{container_name} health check failed: {e}")
        return False
