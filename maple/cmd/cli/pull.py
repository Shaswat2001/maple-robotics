"""
Pull commands for the MAPLE CLI.

This module provides commands for downloading (pulling) policies and
environments from remote repositories or registries. These resources must
be pulled before they can be served and used in evaluations.

Commands:
- policy: Download a policy model
- env: Download an environment image
"""

import typer 
import requests
from rich import print
from maple.utils.config import config
from maple.cmd.cli.misc import daemon_url

# Create the pull sub-application
# no_args_is_help=True ensures help is shown when no command is given
pull_app = typer.Typer(no_args_is_help=True)

@pull_app.command("policy")
def pull_policy(
    name: str,
    port: int = typer.Option(None, "--port")
) -> None:
    """
    Download a policy model.
    
    Pulls a policy model from a remote repository or registry, making it
    available for serving and evaluation. The policy specification can
    include version information (e.g., 'openvla:7b').
    
    :param name: Policy specification string (name or name:version).
    :param port: Daemon port number.
    """
    # Use config default if port not specified
    port = port or config.daemon.port
    
    # Send pull request to daemon with policy spec
    r = requests.post(f"{daemon_url(port)}/policy/pull", json={"spec": name})
    
    if r.status_code != 200:
        print(f"[red]Error:[/red] {r.json()['detail']}")
        raise typer.Exit(1)
    
    # Confirm successful pull
    print(f"[green]PULLED policy[/green] {name}")

@pull_app.command("env")
def pull_env(
    name: str,
    port: int = typer.Option(None, "--port")
) -> None:
    """
    Download an environment image.
    
    Pulls an environment container image from a remote registry, making it
    available for serving and running evaluations. The environment name
    typically corresponds to a Docker image.
    
    :param name: Environment name or image specification.
    :param port: Daemon port number.
    """
    # Use config default if port not specified
    port = port or config.daemon.port
    
    # Send pull request to daemon with environment name
    # Note: Uses query params instead of JSON body (different from policy)
    r = requests.post(f"{daemon_url(port)}/env/pull", params={"name": name})
    
    if r.status_code != 200:
        print(f"[red]Error:[/red] {r.json()['detail']}")
        raise typer.Exit(1)
    
    # Confirm successful pull
    print(f"[bold green]PULL ENV[/bold green] name={name}")