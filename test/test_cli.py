"""
Tests for maple.cmd.maple_cli module.
"""

import pytest
from unittest.mock import MagicMock, patch
from typer.testing import CliRunner


runner = CliRunner()


class TestCLIBasic:
    """Basic CLI tests."""
    
    @pytest.mark.unit
    def test_help(self):
        """Test --help flag."""
        from maple.cmd.maple_cli import app
        
        result = runner.invoke(app, ["--help"])
        
        assert result.exit_code == 0
        assert "maple" in result.output.lower() or "vla" in result.output.lower()
    
    @pytest.mark.unit
    def test_config_show(self, temp_config_dir):
        """Test config show command."""
        from maple.cmd.maple_cli import app
        
        result = runner.invoke(app, ["config", "show"])
        
        # Should show config even without file
        assert result.exit_code == 0
        assert "daemon" in result.output or "port" in result.output
    
    @pytest.mark.unit
    def test_config_path(self, temp_config_dir):
        """Test config path command."""
        from maple.cmd.maple_cli import app
        
        result = runner.invoke(app, ["config", "path"])
        
        assert result.exit_code == 0
        assert ".maple" in result.output or "config" in result.output


class TestServeCommands:
    """Tests for serve commands."""
    
    @pytest.mark.unit
    def test_serve_help(self):
        """Test serve --help."""
        from maple.cmd.maple_cli import app
        
        result = runner.invoke(app, ["serve", "--help"])
        
        assert result.exit_code == 0
        assert "daemon" in result.output.lower() or "serve" in result.output.lower()
    
    @pytest.mark.unit
    def test_serve_policy_help(self):
        """Test serve policy --help."""
        from maple.cmd.maple_cli import app
        
        result = runner.invoke(app, ["serve", "policy", "--help"])
        
        assert result.exit_code == 0
        assert "policy" in result.output.lower()


class TestListCommands:
    """Tests for list commands."""
    
    @pytest.mark.unit
    def test_list_policy_no_daemon(self):
        """Test list policy when daemon not running."""
        from maple.cmd.maple_cli import app
        
        result = runner.invoke(app, ["list", "policy", "--port", "59999"])
        
        # Should fail gracefully
        assert result.exit_code != 0 or "error" in result.output.lower() or "not running" in result.output.lower()
    
    @pytest.mark.unit
    def test_list_env_no_daemon(self):
        """Test list env when daemon not running."""
        from maple.cmd.maple_cli import app
        
        result = runner.invoke(app, ["list", "env", "--port", "59999"])
        
        assert result.exit_code != 0 or "error" in result.output.lower() or "not running" in result.output.lower()


class TestStatusCommand:
    """Tests for status command."""
    
    @pytest.mark.unit
    def test_status_no_daemon(self):
        """Test status when daemon not running."""
        from maple.cmd.maple_cli import app
        
        result = runner.invoke(app, ["status", "--port", "59999"])
        
        assert "not running" in result.output.lower()


class TestEvalCommand:
    """Tests for eval command."""
    
    @pytest.mark.unit
    def test_eval_help(self):
        """Test eval --help."""
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
