"""
Retry utilities file.

This module provides decorators and utilities for automatic retry logic with
exponential backoff. It helps handle transient failures in network operations,
API calls, and other potentially flaky operations.

Key features:
- Configurable retry attempts with exponential backoff
- Exception filtering (retry only specific exception types)
- Maximum delay cap to prevent excessive waiting
- Decorator and functional retry patterns
- Dataclass-based configuration for reusability
- Comprehensive logging of retry attempts

The retry mechanism uses exponential backoff to gradually increase wait times
between attempts, reducing load on failing systems while still providing
reasonable retry intervals for transient failures.

"""

import time
from dataclasses import dataclass
from functools import wraps 
from typing import Callable, Optional, Tuple, Type, TypeVar

from maple.utils.logging import get_logger

log = get_logger("retry")
T = TypeVar("T")

@dataclass
class RetryConfig:
    """
    Configuration container for retry behavior.
    
    Encapsulates all retry parameters in a reusable dataclass. This allows
    creating named retry configurations that can be shared across multiple
    functions or stored as constants.
    """

    max_attempts: int = 3
    """Maximum number of execution attempts before giving up."""
    delay: float = 1.0
    """Initial delay in seconds between retry attempts."""
    backoff: float = 2.0
    """Multiplier applied to delay after each failed attempt."""
    max_delay: float = 30.0
    """Maximum delay cap in seconds."""
    exceptions: Tuple[Type[Exception], ...] = (Exception,)
    """Tuple of exception types to catch and retry on."""

def retry(
    max_attempts: int = 3, 
    delay: float = 1.0,
    backoff: float = 2.0,
    max_delay: float = 30.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    config: Optional[RetryConfig] = None, 
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator that adds automatic retry logic with exponential backoff.
    
    Wraps a function to automatically retry on failure with configurable
    backoff strategy. Useful for handling transient failures in network
    operations, external API calls, or resource contention.
    
    The decorator can be configured either by passing parameters directly
    or by providing a RetryConfig object. If both are provided, the config
    object takes precedence.
    
    :param max_attempts: Maximum number of execution attempts. Must be >= 1.
    :param delay: Initial delay between retries in seconds. Must be >= 0.
    :param backoff: Exponential backoff multiplier. Applied to delay after each failed attempt.
    :param max_delay: Maximum delay cap in seconds. Prevents unbounded growth of retry intervals.
    :param exceptions: Tuple of exception types to catch and retry. Only these
                      exceptions trigger retries; others propagate immediately.
                      Default is (Exception,) which catches all exceptions.
    :param config: Optional RetryConfig object. If provided, overrides all other parameters.
    :return: A decorator function that wraps the target function with retry logic.
    """
    if config:
        max_attempts = config.max_attempts
        delay = config.delay
        backoff = config.backoff
        max_delay = config.max_delay
        exceptions = config.exceptions

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_exception: Optional[Exception] = None
            current_delay = delay
            
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt < max_attempts:
                        log.warning(
                            f"{func.__name__} failed (attempt {attempt}/{max_attempts}): {e}. "
                            f"Retrying in {current_delay:.1f}s..."
                        )
                        time.sleep(current_delay)
                        current_delay = min(current_delay * backoff, max_delay)
                    else:
                        log.error(
                            f"{func.__name__} failed after {max_attempts} attempts: {e}"
                        )
            
            raise last_exception
        
        return wrapper
    return decorator

def retry_call(
    func: Callable[..., T],
    args: tuple = (),
    kwargs: dict = None,
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
) -> T:
    """
    Functional interface for retrying a callable with arguments.
    
    Provides a non-decorator way to add retry logic to a function call.
    Useful when you can't or don't want to use the decorator syntax, or
    when retry behavior needs to be determined at call time.
    
    This function is particularly useful for:
    - One-off retries without modifying function definitions
    - Dynamic retry configuration based on runtime conditions
    - Retrying lambda functions or other callables
    - Testing retry behavior
        
    :param func: The callable to execute with retry logic.
    :param args: Positional arguments to pass to func. Default is empty tuple.
    :param kwargs: Keyword arguments to pass to func. Default is empty dict.
    :param max_attempts: Maximum number of execution attempts. Must be >= 1.
    :param delay: Initial delay between retries in seconds.
    :param backoff: Exponential backoff multiplier applied after each failure.
    :param exceptions: Tuple of exception types to catch and retry on.
                      Default is (Exception,) which catches all exceptions.
    :return: The return value from successful function execution.
    """
    kwargs = kwargs or {}
    
    @retry(
        max_attempts=max_attempts,
        delay=delay,
        backoff=backoff,
        exceptions=exceptions,
    )
    def _call():
        return func(*args, **kwargs)
    
    return _call()
