import logging
import sys
from pathlib import Path
from typing import Optional

_CONFIGURED = False

def setup_logging(
    level: str = "INFO",
    log_file: Optional[Path] = None,
    verbose: bool = False
):
    
    global _CONFIGURED

    if _CONFIGURED:
        return
    
    if verbose:
        fmt = "%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s"
    else:
        fmt = "%(asctime)s | %(levelname)-8s | %(message)s"
    
    datefmt = "%Y-%m-%d %H:%M:%S"
    
    handlers = [logging.StreamHandler(sys.stdout)]
    
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file))
    
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

    return logging.getLogger(f"vla.{name}")
