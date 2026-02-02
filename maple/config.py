import os
import yaml
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field, asdict

from maple.utils.logging import get_logger

log = get_logger("config")

CONFIG_DIR = Path.home() / ".maple"
CONFIG_FILE = CONFIG_DIR / "config.yaml"

@dataclass
class LoggingConfig:
    level: str = "INFO"
    file: Optional[str] = None
    verbose: bool = False


@dataclass
class ContainerConfig:
    memory_limit: str = "32g"
    shm_size: str = "2g"
    startup_timeout: int = 300
    health_check_interval: int = 30


@dataclass
class PolicyConfig:
    default_device: str = "cpu"
    attn_implementation: str = "sdpa"  # sdpa, flash_attention_2, eager
    

@dataclass
class EnvConfig:
    default_num_envs: int = 1


@dataclass
class DaemonConfig:
    host: str = "0.0.0.0"
    port: int = 8000

@dataclass  
class RunConfig:
    max_steps: int = 300
    timeout: int = 200
    save_video: bool = False
    video_dir: str = "~/.maple/videos"

@dataclass  
class EvalConfig:
    max_steps: int = 300
    timeout: int = 200
    save_video: bool = False
    video_dir: str = "~/.maple/videos"
    results_dir: str = "~/.maple/results"

@dataclass
class Config:

    logging: LoggingConfig = field(default_factory=LoggingConfig)
    containers: ContainerConfig = field(default_factory=ContainerConfig)
    policy: PolicyConfig = field(default_factory=PolicyConfig)
    env: EnvConfig = field(default_factory=EnvConfig)
    daemon: DaemonConfig = field(default_factory=DaemonConfig)
    eval: EvalConfig = field(default_factory=EvalConfig)
    run: RunConfig = field(default_factory=RunConfig)
    
    # Convenience aliases
    @property
    def device(self) -> str:
        return self.policy.default_device
    
    @device.setter
    def device(self, value: str):
        self.policy.default_device = value
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    def save(self, path: Path = None):
        """Save config to YAML file."""
        path = path or CONFIG_FILE
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, "w") as f:
            yaml.dump(self.to_dict(), f, default_flow_style=False, sort_keys=False)
        
        log.info(f"Config saved to {path}")

config = Config()

def _deep_update(base: dict, updates: dict) -> dict:
    """Recursively update nested dict."""
    for key, value in updates.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_update(base[key], value)
        else:
            base[key] = value
    return base

def _apply_env_vars(cfg: Config):
    """Apply environment variable overrides (MAPLE_*)."""
    env_mappings = {
        "MAPLE_DEVICE": ("policy", "default_device"),
        "MAPLE_ATTN": ("policy", "attn_implementation"),
        "MAPLE_LOG_LEVEL": ("logging", "level"),
        "MAPLE_LOG_FILE": ("logging", "file"),
        "MAPLE_MEMORY_LIMIT": ("containers", "memory_limit"),
        "MAPLE_STARTUP_TIMEOUT": ("containers", "startup_timeout"),
        "MAPLE_DAEMON_PORT": ("daemon", "port"),
        "MAPLE_MAX_STEPS": ("eval", "max_steps"),
        "MAPLE_SAVE_VIDEO": ("eval", "save_video"),
    }
    
    for env_var, (section, key) in env_mappings.items():
        value = os.environ.get(env_var)
        if value is not None:
            section_obj = getattr(cfg, section)
            
            # Type conversion
            current = getattr(section_obj, key)
            if isinstance(current, bool):
                value = value.lower() in ("true", "1", "yes")
            elif isinstance(current, int):
                value = int(value)
            
            setattr(section_obj, key, value)
            log.debug(f"Config override from {env_var}: {section}.{key} = {value}")

def _load_from_dict(cfg: Config, data: dict):
    """Load config values from a dictionary."""
    if "logging" in data:
        for k, v in data["logging"].items():
            if hasattr(cfg.logging, k):
                setattr(cfg.logging, k, v)
    
    if "containers" in data:
        for k, v in data["containers"].items():
            if hasattr(cfg.containers, k):
                setattr(cfg.containers, k, v)
    
    if "policy" in data:
        for k, v in data["policy"].items():
            if hasattr(cfg.policy, k):
                setattr(cfg.policy, k, v)
    
    if "env" in data:
        for k, v in data["env"].items():
            if hasattr(cfg.env, k):
                setattr(cfg.env, k, v)
    
    if "daemon" in data:
        for k, v in data["daemon"].items():
            if hasattr(cfg.daemon, k):
                setattr(cfg.daemon, k, v)
    
    if "eval" in data:
        for k, v in data["eval"].items():
            if hasattr(cfg.eval, k):
                setattr(cfg.eval, k, v)

    if "run" in data:
        for k, v in data["run"].items():
            if hasattr(cfg.run, k):
                setattr(cfg.run, k, v)

def load_config(config_path: Path = None) -> Config:

    global config
    
    # Reset to defaults
    config = Config()
    
    # Load from file
    path = config_path or CONFIG_FILE
    if path.exists():
        try:
            with open(path) as f:
                data = yaml.safe_load(f) or {}
            _load_from_dict(config, data)
            log.debug(f"Loaded config from {path}")
        except Exception as e:
            log.warning(f"Failed to load config from {path}: {e}")
    
    # Apply environment variables
    _apply_env_vars(config)
    
    return config

def init_config_file():
    """Create default config file if it doesn't exist."""
    if not CONFIG_FILE.exists():
        config.save(CONFIG_FILE)
        log.info(f"Created default config at {CONFIG_FILE}")

def get_config() -> Config:
    """Get the global config instance."""
    return config
