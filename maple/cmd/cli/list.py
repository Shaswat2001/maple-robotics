"""
List commands for the MAPLE CLI.

This module provides commands for listing available resources managed by
the MAPLE daemon. It allows users to view registered policies and environments
that are available for use in evaluations.

Commands:
- policy: List all available policy containers
- env: List all available environment containers
"""

import typer 
import requests
from rich import print
from maple.utils.config import get_config
from maple.utils.misc import daemon_url

# Create the list sub-application
# no_args_is_help=True ensures help is shown when no command is given
list_app = typer.Typer(no_args_is_help=True)

@list_app.command("policy")
def list_policy(port: int = typer.Option(None, "--port")) -> None:
    """
    List all available policy containers.
    
    Queries the daemon and displays all registered policy containers that
    are available for running evaluations. Shows policy identifiers and
    their current status.
    
    :param port: Daemon port number.
    """
    config = get_config()
    # Use config default if port not specified
    port = port or config.daemon.port
    
    # Request policy list from daemon
    r = requests.get(f"{daemon_url(port)}/policy/list")
    
    # Display policies
    print("[yellow]Policies:[/yellow]", r.json()["policies"])

@list_app.command("env")
def list_env(port: int = typer.Option(None, "--port")) -> None:
    """
    List all available environment containers.
    
    Queries the daemon and displays all registered environment containers
    that are available for running evaluations. Shows environment identifiers
    and their current status.
    
    :param port: Daemon port number.
    """
    config = get_config()
    # Use config default if port not specified
    port = port or config.daemon.port
    
    # Request environment list from daemon
    r = requests.get(f"{daemon_url(port)}/env/list")
    
    # Display environments
    print("[yellow]Envs:[/yellow]", r.json()["envs"])