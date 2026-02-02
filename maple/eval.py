import json
import time
import uuid
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field, asdict
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from maple.utils.logging import get_logger
from maple.state import store
from maple.config import config

log = get_logger("eval")

@dataclass
class EvalResult:
    """Result of a single evaluation episode."""
    run_id: str
    policy_id: str
    env_id: str
    task: str
    instruction: str
    seed: int
    
    # Outcomes
    steps: int = 0
    total_reward: float = 0.0
    success: bool = False
    terminated: bool = False
    truncated: bool = False
    
    # Timing
    started_at: float = 0.0
    finished_at: float = 0.0
    duration_seconds: float = 0.0
    
    # Optional
    video_path: Optional[str] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, d: dict) -> "EvalResult":
        return cls(**d)
