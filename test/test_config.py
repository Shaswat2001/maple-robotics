"""
Tests for maple.config module.
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
        assert default_config.policy.attn_implementation == "sdpa"
        assert default_config.containers.memory_limit == "32g"
        assert default_config.eval.max_steps == 300
        assert default_config.eval.save_video is False
    
    @pytest.mark.unit
    def test_device_alias(self, default_config):
        """Test device property alias."""
        assert default_config.device == "cpu"
        
        default_config.device = "cuda:1"
        assert default_config.policy.default_device == "cuda:1"
    
    @pytest.mark.unit
    def test_to_dict(self, default_config):
        """Test config serialization to dict."""
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
        """Test saving config to file."""
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
        """Test loading with no config file (uses defaults)."""
        from maple.utils.config import load_config, config
        
        load_config()
        
        assert config.daemon.port == 8000
        assert config.policy.default_device == "cpu"
    
    @pytest.mark.unit
    def test_load_from_file(self, config_file, temp_config_dir):
        """Test loading from config file."""
        from maple.utils.config import load_config, config
        
        load_config(config_file)
        
        assert config.daemon.port == 8000
        assert config.policy.default_device == "cpu"
        assert config.logging.level == "INFO"
        assert config.eval.max_steps == 300
    
    @pytest.mark.unit
    def test_env_var_override(self, temp_config_dir, monkeypatch):
        """Test environment variable overrides."""
        from maple.utils.config import load_config, config
        
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


class TestInitConfigFile:
    """Tests for init_config_file function."""
    
    @pytest.mark.unit
    def test_creates_file(self, temp_config_dir):
        """Test that init creates config file."""
        from maple.utils.config import init_config_file, CONFIG_FILE
        
        # Ensure file doesn't exist
        if CONFIG_FILE.exists():
            CONFIG_FILE.unlink()
        
        init_config_file()
        
        # Check file was created in temp dir
        expected_path = temp_config_dir / "config.yaml"
        # Note: CONFIG_FILE points to real home, so we check temp dir
