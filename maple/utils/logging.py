"""
Centralized logging configuration.

This module provides a consistent logging setup across all MAPLE components.
It configures Python's standard logging with appropriate formatters, handlers,
and log levels, and provides a factory function for creating namespaced loggers.

Key features:
- Centralized configuration to prevent duplicate setup
- Configurable log levels (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- Optional file logging alongside console output
- Verbose mode with source location information
- Automatic suppression of noisy third-party library logs
- Namespaced loggers with "maple." prefix for MAPLE components

The module uses a global flag to ensure logging is only configured once,
even if setup_logging() is called multiple times. All MAPLE loggers use
the "maple." namespace prefix for easy filtering.
"""

import logging
import sys
from pathlib import Path
from typing import Optional

_CONFIGURED = False

def setup_logging(level: str = "INFO",
                  log_file: Optional[Path] = None,
                  verbose: bool = False
                  ) -> None:
    """
    Configure the global logging system for MAPLE.
    
    Sets up Python's logging module with consistent formatting, handlers,
    and log levels. This should be called once at application startup,
    typically in the main entry point or CLI initialization.
    
    Safe to call multiple times - subsequent calls are ignored to prevent
    duplicate handler registration and conflicting configurations.
    
    The function configures:
    - Log message format (timestamp, level, message, optionally source location)
    - Console output handler (stdout)
    - Optional file output handler
    - Third-party library log level suppression
    
    Verbose mode adds source location information (module:line) to each
    log message, useful for debugging but cluttering for normal operation.
    
    :param level: Logging level as string. Valid values: "DEBUG", "INFO",
                 "WARNING", "ERROR", "CRITICAL". Case-insensitive.
                 Defaults to "INFO".
    :param log_file: Optional path to write logs to a file. The parent
                    directory will be created if it doesn't exist.
                    If None, only console logging is enabled.
    :param verbose: If True, includes source module and line number in
                   log messages. If False, uses simpler format with just
                   timestamp, level, and message. Defaults to False.
    """
    global _CONFIGURED
    if _CONFIGURED:
        return

    # Configure message format based on verbosity
    if verbose:
        fmt = "%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s"
    else:
        fmt = "%(asctime)s | %(levelname)-8s | %(message)s"

    datefmt = "%Y-%m-%d %H:%M:%S"

    # Setup handlers
    handlers = [logging.StreamHandler(sys.stdout)]
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file))

    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format=fmt,
        datefmt=datefmt,
        handlers=handlers,
    )

    # Quiet noisy third-party loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("docker").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """
    Create a namespaced logger for MAPLE components.
    
    Returns a Python logger with the "maple." prefix prepended to the
    given name. This provides consistent namespacing for all MAPLE
    framework loggers, making it easy to filter and configure them
    separately from other libraries.
    
    The returned logger inherits configuration from the root logger
    set up by setup_logging(), including log level, format, and handlers.
    
    :param name: Component name for the logger, typically the module
                name or functional area (e.g., "policy.base", "cleanup",
                "health"). The "maple." prefix is automatically added.
    :return: Configured logging.Logger instance with "maple." namespace.
    """
    return logging.getLogger(f"maple.{name}")