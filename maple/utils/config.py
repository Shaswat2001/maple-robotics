"""
Configuration management for MAPLE.

This module provides a hierarchical configuration system for MAPLE with support
for YAML files, environment variable overrides, and programmatic access. The
configuration covers all aspects of MAPLE operation including logging, container
settings, policy/environment defaults, daemon settings, and evaluation parameters.

Configuration sources (in order of precedence):
1. Environment variables (MAPLE_* prefix)
2. YAML configuration file (~/.maple/config.yaml)
3. Default values defined in dataclasses

Key features:
- Hierarchical configuration with nested sections
- Type-safe dataclass-based configuration
- YAML file persistence
- Environment variable overrides
- Global singleton instance
- Convenience property aliases

Configuration sections:
- logging: Log level, file output, verbosity
- containers: Docker container limits and timeouts
- policy: Default device and attention implementation
- env: Environment-specific defaults
- daemon: Server host and port
- run: Single episode execution settings
- eval: Batch evaluation settings
"""

import os
import yaml
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass, field, asdict

from maple.utils.logging import get_logger

log = get_logger("config")

# Configuration directory and file paths
CONFIG_DIR = Path.home() / ".maple"
CONFIG_FILE = CONFIG_DIR / "config.yaml"

@dataclass
class LoggingConfig:
    """
    Logging configuration section.
    """
    # Log level: DEBUG, INFO, WARNING, ERROR, CRITICAL
    level: str = "INFO"
    # Optional path to log file (None = stderr only)
    file: Optional[str] = None
    # Enable verbose output with additional debug info
    verbose: bool = False

@dataclass
class ContainerConfig:
    """
    Docker container configuration section.
    """
    # Memory limit for containers (e.g., '32g', '16g')
    memory_limit: str = "32g"
    # Shared memory size for PyTorch dataloaders (important for multiprocessing)
    shm_size: str = "2g"
    # Maximum seconds to wait for container startup
    startup_timeout: int = 300
    # Seconds between container health check polls
    health_check_interval: int = 30

@dataclass
class PolicyConfig:
    """
    Policy backend configuration section.
    """
    # Default device for policy models ('cpu', 'cuda:0', etc.)
    default_device: str = "cpu"
    # Default model kwargs
    model_kwargs: Dict[str, Any] = field(default_factory=dict) # Used during act
    model_load_kwargs: Dict[str, Any] = field(default_factory=dict) # Used during serve

@dataclass
class EnvConfig:
    """
    Environment backend configuration section.
    """
    # Default device for env ('cpu', 'cuda:0', etc.)
    default_device: str = "cpu"
    # Default number of environment instances to create when serving
    default_num_envs: int = 1
    env_kwargs: Dict[str, Any] = field(default_factory=dict)

@dataclass
class DaemonConfig:
    """
    Daemon server configuration section.
    """
    # Host address to bind the daemon server to (0.0.0.0 = all interfaces)
    host: str = "0.0.0.0"
    # Port number for the daemon HTTP API
    port: int = 8000

@dataclass  
class RunConfig:
    """
    Single episode run configuration section.
    """
    # Maximum steps per episode before truncation
    max_steps: int = 300
    # Timeout multiplier for HTTP requests (actual timeout = max_steps * multiplier)
    timeout: int = 200
    # Whether to record and save episode videos by default
    save_video: bool = False
    # Directory for saving episode videos
    video_dir: Optional[str] = None

@dataclass  
class EvalConfig:
    """
    Batch evaluation configuration section.
    """
    # Maximum steps per episode before truncation
    max_steps: int = 300
    # Timeout multiplier for HTTP requests
    timeout: int = 200
    # Whether to record and save evaluation videos by default
    save_video: bool = False
    # Directory for saving evaluation videos
    video_dir: str = "~/.maple/videos"
    # Directory for saving evaluation results and metrics
    results_dir: str = "~/.maple/results"


@dataclass
class Config:
    """
    Root configuration container for MAPLE.
    
    Provides access to all configuration sections and convenience methods
    for persistence and manipulation. Uses dataclass fields with factory
    functions to ensure each section has independent default instances.
    """

    # Configuration sections (use factories to create independent instances)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    containers: ContainerConfig = field(default_factory=ContainerConfig)
    policy: PolicyConfig = field(default_factory=PolicyConfig)
    env: EnvConfig = field(default_factory=EnvConfig)
    daemon: DaemonConfig = field(default_factory=DaemonConfig)
    eval: EvalConfig = field(default_factory=EvalConfig)
    run: RunConfig = field(default_factory=RunConfig)
    
    # Convenience aliases for commonly accessed settings
    @property
    def device(self) -> str:
        """
        Convenience property for accessing default device.
        
        :return: Default device string from policy configuration.
        """
        return self.policy.default_device
    
    @device.setter
    def device(self, value: str) -> None:
        """
        Convenience setter for default device.
        
        :param value: Device string to set ('cpu', 'cuda:0', etc.).
        """
        self.policy.default_device = value
    
    def to_dict(self) -> dict:
        """
        Convert configuration to dictionary.
        
        :return: Nested dictionary representation of all configuration sections.
        """
        # asdict recursively converts dataclasses to dictionaries
        return asdict(self)
    
    def save(self, path: Path = None) -> None:
        """
        Save configuration to YAML file.
        
        Creates parent directories if they don't exist. The saved file
        preserves the hierarchical structure and uses human-readable
        YAML formatting.
        
        :param path: Path to save config file (default: ~/.maple/config.yaml).
        """
        # Use default path if not specified
        path = path or CONFIG_FILE
        
        # Create parent directory if needed
        path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write YAML with readable formatting
        with open(path, "w") as f:
            yaml.dump(
                self.to_dict(),
                f,
                default_flow_style=False,  # Use block style (multi-line) instead of inline
                sort_keys=False  # Preserve field order from dataclass definition
            )
        
        log.info(f"Config saved to {path}")

# Global configuration instance
# This singleton is accessed throughout MAPLE for configuration values
config = Config()

def _deep_update(base: Dict, updates: Dict) -> Dict:
    """
    Recursively update nested dictionary.
    
    Merges the updates dictionary into the base dictionary, handling
    nested dictionaries recursively. Used for combining configuration
    from multiple sources.
    
    :param base: Base dictionary to update.
    :param updates: Dictionary with updates to apply.
    :return: Updated base dictionary (modified in-place).
    """
    for key, value in updates.items():
        # Recursively merge nested dictionaries
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            # Both are dicts - recurse to merge
            _deep_update(base[key], value)
        else:
            # Direct assignment for non-dict values or new keys
            base[key] = value
    return base


def _apply_env_vars(cfg: Config) -> None:
    """
    Apply environment variable overrides to configuration.
    
    Checks for MAPLE_* environment variables and applies them as overrides
    to the configuration. Environment variables take precedence over file
    configuration. Handles type conversion based on the target field type.
    
    :param cfg: Configuration instance to update.
    """
    # Map environment variables to (section, key) tuples
    # This defines which env vars map to which config fields
    env_mappings = {
        "MAPLE_DEVICE": ("policy", "default_device"),
        "MAPLE_LOG_LEVEL": ("logging", "level"),
        "MAPLE_LOG_FILE": ("logging", "file"),
        "MAPLE_MEMORY_LIMIT": ("containers", "memory_limit"),
        "MAPLE_STARTUP_TIMEOUT": ("containers", "startup_timeout"),
        "MAPLE_DAEMON_PORT": ("daemon", "port"),
        "MAPLE_MAX_STEPS": ("eval", "max_steps"),
        "MAPLE_SAVE_VIDEO": ("eval", "save_video"),
    }
    
    # Process each potential environment variable
    for env_var, (section, key) in env_mappings.items():
        value = os.environ.get(env_var)
        if value is not None:
            # Get the configuration section object (e.g., cfg.policy)
            section_obj = getattr(cfg, section)
            
            # Get current value to determine expected type
            current = getattr(section_obj, key)
            
            # Type conversion based on current value type
            if isinstance(current, bool):
                # Parse boolean from string (case-insensitive)
                value = value.lower() in ("true", "1", "yes")
            elif isinstance(current, int):
                # Parse integer from string
                value = int(value)
            # Strings are used as-is, no conversion needed
            
            # Apply the override to the config object
            setattr(section_obj, key, value)
            log.debug(f"Config override from {env_var}: {section}.{key} = {value}")


def _load_from_dict(cfg: Config, data: Dict) -> None:
    """
    Load configuration values from a dictionary.
    
    Updates the configuration object with values from a nested dictionary
    (typically loaded from YAML). Only updates fields that exist in the
    configuration dataclasses to avoid errors from unknown keys.
    
    :param cfg: Configuration instance to update.
    :param data: Nested dictionary with configuration values.
    """
    # Update logging section
    if "logging" in data:
        for k, v in data["logging"].items():
            # Only set if the attribute exists (ignore unknown keys)
            if hasattr(cfg.logging, k):
                setattr(cfg.logging, k, v)
    
    # Update containers section
    if "containers" in data:
        for k, v in data["containers"].items():
            if hasattr(cfg.containers, k):
                setattr(cfg.containers, k, v)
    
    # Update policy section
    if "policy" in data:
        for k, v in data["policy"].items():
            if hasattr(cfg.policy, k):
                setattr(cfg.policy, k, v)
    
    # Update env section
    if "env" in data:
        for k, v in data["env"].items():
            if hasattr(cfg.env, k):
                setattr(cfg.env, k, v)
    
    # Update daemon section
    if "daemon" in data:
        for k, v in data["daemon"].items():
            if hasattr(cfg.daemon, k):
                setattr(cfg.daemon, k, v)
    
    # Update eval section
    if "eval" in data:
        for k, v in data["eval"].items():
            if hasattr(cfg.eval, k):
                setattr(cfg.eval, k, v)

    # Update run section
    if "run" in data:
        for k, v in data["run"].items():
            if hasattr(cfg.run, k):
                setattr(cfg.run, k, v)

def load_config(config_path: Path = None) -> Config:
    """
    Load configuration from file and environment variables.
    
    Loads configuration in the following order:
    1. Reset to default values
    2. Load from YAML file (if exists)
    3. Apply environment variable overrides
    
    Updates the global config instance and returns it. This function
    should be called early in application startup to initialize
    configuration.
    
    :param config_path: Optional path to config file (default: ~/.maple/config.yaml).
    :return: Updated global configuration instance.
    """
    global config
    
    # Reset to default values (fresh start)
    config = Config()
    
    # Load from YAML file (if it exists)
    path = config_path or CONFIG_FILE
    if path.exists():
        try:
            # Load YAML file
            with open(path) as f:
                data = yaml.safe_load(f) or {}
            # Apply values from file to config object
            _load_from_dict(config, data)
            log.debug(f"Loaded config from {path}")
        except Exception as e:
            # Log warning but continue with defaults + env vars
            log.warning(f"Failed to load config from {path}: {e}")
    
    # Apply environment variable overrides (highest precedence)
    _apply_env_vars(config)
    return config

def init_config_file():
    """
    Create default configuration file if it doesn't exist.
    
    Generates a new config file with default values at the standard
    location (~/.maple/config.yaml). Safe to call multiple times as
    it only creates the file if missing.
    """
    # Only create if file doesn't already exist
    if not CONFIG_FILE.exists():
        # Save current config (with defaults) to file
        config.save(CONFIG_FILE)
        log.info(f"Created default config at {CONFIG_FILE}")

def get_config() -> Config:
    """
    Get the global configuration instance.
    
    Returns the singleton configuration object used throughout MAPLE.
    This is the primary way to access configuration values.
    
    :return: Global configuration instance.
    """
    return config
