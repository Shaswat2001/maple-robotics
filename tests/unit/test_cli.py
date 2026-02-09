"""
Unit tests for maple.cmd.maple_cli module.

Tests cover:
- Basic CLI help and version
- Config subcommands
- Serve subcommands
- List subcommands
- Status command
- Eval command
"""

import pytest
from unittest.mock import MagicMock, patch
from typer.testing import CliRunner


runner = CliRunner()


class TestCLIBasic:
    """Basic CLI tests."""
    
    @pytest.mark.unit
    def test_help(self):
        """Test --help flag displays usage."""
        from maple.cmd.maple_cli import app
        
        result = runner.invoke(app, ["--help"])
        
        assert result.exit_code == 0
        assert "maple" in result.output.lower() or "vla" in result.output.lower()
    
    @pytest.mark.unit
    def test_version_help_available(self):
        """Test that version info is accessible."""
        from maple.cmd.maple_cli import app
        
        # Version should be mentioned in help or available as flag
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0


class TestConfigCommands:
    """Tests for config subcommands."""
    
    @pytest.mark.unit
    def test_config_show(self, temp_config_dir):
        """Test config show command displays configuration."""
        from maple.cmd.maple_cli import app
        
        result = runner.invoke(app, ["config", "show"])
        
        # Should show config even without file
        assert result.exit_code == 0
        assert "daemon" in result.output or "port" in result.output
    
    @pytest.mark.unit
    def test_config_path(self, temp_config_dir):
        """Test config path command shows config file location."""
        from maple.cmd.maple_cli import app
        
        result = runner.invoke(app, ["config", "path"])
        
        assert result.exit_code == 0
        assert ".maple" in result.output or "config" in result.output
    
    @pytest.mark.unit
    def test_config_help(self):
        """Test config --help shows available subcommands."""
        from maple.cmd.maple_cli import app
        
        result = runner.invoke(app, ["config", "--help"])
        
        assert result.exit_code == 0
        assert "show" in result.output.lower()


class TestServeCommands:
    """Tests for serve subcommands."""
    
    @pytest.mark.unit
    def test_serve_help(self):
        """Test serve --help shows available options."""
        from maple.cmd.maple_cli import app
        
        result = runner.invoke(app, ["serve", "--help"])
        
        assert result.exit_code == 0
        assert "daemon" in result.output.lower() or "serve" in result.output.lower()
    
    @pytest.mark.unit
    def test_serve_policy_help(self):
        """Test serve policy --help shows policy options."""
        from maple.cmd.maple_cli import app
        
        result = runner.invoke(app, ["serve", "policy", "--help"])
        
        assert result.exit_code == 0
        assert "policy" in result.output.lower()
    
    @pytest.mark.unit
    def test_serve_env_help(self):
        """Test serve env --help shows environment options."""
        from maple.cmd.maple_cli import app
        
        result = runner.invoke(app, ["serve", "env", "--help"])
        
        assert result.exit_code == 0


class TestListCommands:
    """Tests for list subcommands."""
    
    @pytest.mark.unit
    def test_list_policy_no_daemon(self):
        """Test list policy fails gracefully when daemon not running."""
        from maple.cmd.maple_cli import app
        
        result = runner.invoke(app, ["list", "policy", "--port", "59999"])
        
        # Should fail gracefully with helpful message
        assert (
            result.exit_code != 0 or 
            "error" in result.output.lower() or 
            "not running" in result.output.lower()
        )
    
    @pytest.mark.unit
    def test_list_env_no_daemon(self):
        """Test list env fails gracefully when daemon not running."""
        from maple.cmd.maple_cli import app
        
        result = runner.invoke(app, ["list", "env", "--port", "59999"])
        
        assert (
            result.exit_code != 0 or 
            "error" in result.output.lower() or 
            "not running" in result.output.lower()
        )
    
    @pytest.mark.unit
    def test_list_help(self):
        """Test list --help shows available subcommands."""
        from maple.cmd.maple_cli import app
        
        result = runner.invoke(app, ["list", "--help"])
        
        assert result.exit_code == 0


class TestStatusCommand:
    """Tests for status command."""
    
    @pytest.mark.unit
    def test_status_no_daemon(self):
        """Test status shows not running when daemon is down."""
        from maple.cmd.maple_cli import app
        
        result = runner.invoke(app, ["status", "--port", "59999"])
        
        assert "not running" in result.output.lower()
    
    @pytest.mark.unit
    def test_status_help(self):
        """Test status --help shows options."""
        from maple.cmd.maple_cli import app
        
        result = runner.invoke(app, ["status", "--help"])
        
        assert result.exit_code == 0


class TestEvalCommand:
    """Tests for eval command."""
    
    @pytest.mark.unit
    def test_eval_help(self):
        """Test eval --help shows all required options."""
        from maple.cmd.maple_cli import app
        
        result = runner.invoke(app, ["eval", "--help"])
        
        assert result.exit_code == 0
        assert "tasks" in result.output.lower()
        assert "seeds" in result.output.lower()
    
    @pytest.mark.unit
    def test_eval_requires_arguments(self):
        """Test that eval requires policy_id and env_id."""
        from maple.cmd.maple_cli import app
        
        result = runner.invoke(app, ["eval"])
        
        # Should fail due to missing required arguments
        assert result.exit_code != 0
    
    @pytest.mark.unit
    def test_eval_missing_policy(self):
        """Test eval fails with missing policy argument."""
        from maple.cmd.maple_cli import app
        
        result = runner.invoke(app, ["eval", "--env-id", "test-env"])
        
        # Should fail or show error
        assert result.exit_code != 0


class TestStopCommand:
    """Tests for stop command."""
    
    @pytest.mark.unit
    def test_stop_help(self):
        """Test stop --help shows options."""
        from maple.cmd.maple_cli import app
        
        result = runner.invoke(app, ["stop", "--help"])
        
        assert result.exit_code == 0
