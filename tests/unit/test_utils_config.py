"""
Unit tests for maple.utils.config module.

Tests cover:
- Config dataclass defaults and properties
- Config serialization/deserialization
- Config file loading and saving
- Environment variable overrides
"""

import os
import pytest
from pathlib import Path


class TestConfig:
    """Tests for Config dataclass."""
    
    @pytest.mark.unit
    def test_default_values(self, default_config):
        """Test that default config has expected values."""
        assert default_config.daemon.port == 8000
        assert default_config.daemon.host == "0.0.0.0"
        assert default_config.policy.default_device == "cpu"
        assert default_config.containers.memory_limit == "32g"
        assert default_config.eval.max_steps == 300
        assert default_config.eval.save_video is False
    
    @pytest.mark.unit
    def test_device_alias(self, default_config):
        """Test device property alias for policy.default_device."""
        assert default_config.device == "cpu"
        
        default_config.device = "cuda:1"
        assert default_config.policy.default_device == "cuda:1"
    
    @pytest.mark.unit
    def test_to_dict(self, default_config):
        """Test config serialization to dictionary."""
        d = default_config.to_dict()
        
        assert isinstance(d, dict)
        assert "logging" in d
        assert "daemon" in d
        assert "policy" in d
        assert "containers" in d
        assert "eval" in d
        
        assert d["daemon"]["port"] == 8000
        assert d["policy"]["default_device"] == "cpu"
    
    @pytest.mark.unit
    def test_save_config(self, default_config, temp_dir):
        """Test saving config to a YAML file."""
        config_path = temp_dir / "test_config.yaml"
        default_config.save(config_path)
        
        assert config_path.exists()
        
        content = config_path.read_text()
        assert "daemon:" in content
        assert "port:" in content


class TestLoadConfig:
    """Tests for load_config function."""
    
    @pytest.mark.unit
    def test_load_default(self, temp_config_dir):
        """Test loading config with no file (uses defaults)."""
        from maple.utils.config import load_config
        
        config = load_config()
        
        assert config.daemon.port == 8000
        assert config.policy.default_device == "cpu"
    
    @pytest.mark.unit
    def test_load_from_file(self, config_file, temp_config_dir):
        """Test loading config from a YAML file."""
        from maple.utils.config import load_config
        
        config = load_config(config_file)
        
        # File values should be loaded where valid
        assert config.daemon.port == 9999  # Default since file has invalid YAML
        assert config.logging.level == "DEBUG"  # Default
    
    @pytest.mark.unit
    def test_env_var_override(self, temp_config_dir, monkeypatch):
        """Test environment variable overrides."""
        monkeypatch.setenv("MAPLE_DEVICE", "cuda:2")
        monkeypatch.setenv("MAPLE_DAEMON_PORT", "7777")
        monkeypatch.setenv("MAPLE_MAX_STEPS", "500")
        
        # Need to reimport to pick up env vars
        import importlib
        import maple.utils.config
        importlib.reload(maple.utils.config)
        from maple.utils.config import load_config
        
        config = load_config()
        
        assert config.policy.default_device == "cuda:2"
        assert config.daemon.port == 7777
        assert config.eval.max_steps == 500


class TestConfigSections:
    """Tests for individual config sections."""
    
    @pytest.mark.unit
    def test_logging_config_defaults(self):
        """Test LoggingConfig defaults."""
        from maple.utils.config import LoggingConfig
        
        cfg = LoggingConfig()
        
        assert cfg.level == "INFO"
        assert cfg.file is None
        assert cfg.verbose is False
    
    @pytest.mark.unit
    def test_container_config_defaults(self):
        """Test ContainerConfig defaults."""
        from maple.utils.config import ContainerConfig
        
        cfg = ContainerConfig()
        
        assert cfg.memory_limit == "32g"
        assert cfg.shm_size == "2g"
        assert cfg.startup_timeout == 300
        assert cfg.health_check_interval == 30
    
    @pytest.mark.unit
    def test_daemon_config_defaults(self):
        """Test DaemonConfig defaults."""
        from maple.utils.config import DaemonConfig
        
        cfg = DaemonConfig()
        
        assert cfg.host == "0.0.0.0"
        assert cfg.port == 8000
    
    @pytest.mark.unit
    def test_eval_config_defaults(self):
        """Test EvalConfig defaults."""
        from maple.utils.config import EvalConfig
        
        cfg = EvalConfig()
        
        assert cfg.max_steps == 300
        assert cfg.save_video is False


class TestGetConfig:
    """Tests for get_config function."""
    
    @pytest.mark.unit
    def test_get_config_returns_instance(self):
        """Test that get_config returns Config instance."""
        from maple.utils.config import get_config, Config
        
        config = get_config()
        
        assert isinstance(config, Config)
    
    @pytest.mark.unit
    def test_get_config_is_singleton(self):
        """Test that get_config returns same instance."""
        from maple.utils.config import get_config
        
        config1 = get_config()
        config2 = get_config()
        
        assert config1 is config2
