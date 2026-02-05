"""
Configuration management commands for the MAPLE CLI.

This module provides commands for viewing, initializing, and managing the
MAPLE configuration file. It allows users to inspect current settings,
create default configuration files, and locate the config file path.

Commands:
- show: Display current configuration with all settings
- init: Create a default configuration file
- path: Show the path to the configuration file
"""

import yaml
import typer 
from rich import print
from maple.utils.config import get_config, CONFIG_FILE

# Create the config sub-application
# no_args_is_help=True ensures help is shown when no command is given
config_app = typer.Typer(no_args_is_help=True)

@config_app.command("show")
def config_show() -> None:
    """
    Show current configuration.
    
    Displays the current MAPLE configuration settings in YAML format.
    This includes all configuration sections (daemon, logging, run, eval, etc.)
    with their current values, whether from the config file or defaults.
    """
    config = get_config()
    print("[cyan]Current configuration:[/cyan]\n")
    # Convert config to dict and dump as YAML for readable output
    # default_flow_style=False ensures block style (multi-line)
    # sort_keys=False preserves the original key order
    print(yaml.dump(config.to_dict(), default_flow_style=False, sort_keys=False))

@config_app.command("init")
def config_init(force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing config")) -> None:
    """
    Create default config file.
    
    Generates a new configuration file with default values at the standard
    config location. If a config file already exists, requires the --force
    flag to overwrite it, preventing accidental loss of custom settings.
    
    :param force: If True, overwrite existing config file without prompting.
    """
    config = get_config()
    # Check if config already exists
    if CONFIG_FILE.exists() and not force:
        # Warn user and exit without making changes
        print(f"[yellow]Config already exists:[/yellow] {CONFIG_FILE}")
        print("Use --force to overwrite")
        return
    
    # Save config to file (creates parent directories if needed)
    config.save(CONFIG_FILE)
    print(f"[green]✓ Config created:[/green] {CONFIG_FILE}")

@config_app.command("path")
def config_path() -> None:
    """
    Show config file path.
    
    Prints the filesystem path where MAPLE looks for its configuration file.
    Useful for locating the config file for manual editing or troubleshooting.
    """
    # Simply print the path - no additional formatting needed
    print(CONFIG_FILE)