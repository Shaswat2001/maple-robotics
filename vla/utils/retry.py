import time
from dataclasses import dataclass
from functools import wraps 
from typing import Callable, Optional, Tuple, Type, TypeVar

from vla.utils.logging import get_logger

log = get_logger("retry")
T = TypeVar("T")

@dataclass
class RetryConfig:

    max_attempts: int = 3
    delay: float = 1.0
    backoff: float = 2.0
    max_delay: float = 30.0
    exceptions: Tuple[Type[Exception], ...] = (Exception,)

def retry(
    max_attempts: int = 3, 
    delay: float = 1.0,
    backoff: float = 2.0,
    max_delay: float = 30.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    config: Optional[RetryConfig] = None, 
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    
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
