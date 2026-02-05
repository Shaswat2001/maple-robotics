"""
Policy management commands for the MAPLE CLI.

This module provides commands for interacting with running policy containers.
It allows users to query policy information and stop policy containers.

Commands:
- info: Display metadata about a policy container
- stop: Stop a specific policy container
"""

import typer 
import requests
from rich import print
from maple.utils.config import get_config
from maple.cmd.cli.misc import daemon_url

# Create the policy sub-application
# no_args_is_help=True ensures help is shown when no command is given
policy_app = typer.Typer(no_args_is_help=True)

@policy_app.command("info")
def policy_info(
    policy_id: str = typer.Argument(..., help="Policy ID (e.g., openvla-latest-fe56e09d)"),
    port: int = typer.Option(None, "--port")
) -> None:
    """
    Display information about a policy container.
    
    Retrieves and displays metadata about a running policy container,
    including input specifications, output specifications, and version
    information.
    
    :param port: Daemon port number.
    :param policy_id: Identifier of the policy container.
    """
    config = get_config()
    # Use config default if port not specified
    port = port or config.daemon.port
    
    # Request policy info from daemon
    r = requests.get(f"{daemon_url(port)}/policy/info/{policy_id}")
    
    if r.status_code != 200:
        print(f"[red]Error:[/red] {r.json().get('detail', 'Unknown error')}")
        raise typer.Exit(1)
    
    # Display policy metadata
    data = r.json()
    print(f"[cyan]Policy Info:[/cyan]")
    print(f"  Name: {data.get('name')}")
    print(f"  Loaded: {data.get('loaded')}")
    print(f"  Model Path: {data.get('model_path')}")
    print(f"  Device: {data.get('device')}")
    print(f"  Image Size: {data.get('image_size')}")

@policy_app.command("stop")
def stop_policy(
    policy_id: str = typer.Argument(..., help="Policy ID (e.g., openvla-latest-fe56e09d)"),
    port: int = typer.Option(None, "--port"),
) -> None:
    """
    Stop a specific policy container.
    
    Sends a stop request to the daemon to terminate a running policy
    container and free its resources.
    
    :param port: Daemon port number.
    :param policy_id: Identifier of the policy container to stop.
    """
    config = get_config()
    # Use config default if port not specified
    port = port or config.daemon.port
    
    # Validate required parameter
    if policy_id is None:
        print(f"[red]Error: Policy id is None[/red]")
        raise typer.Exit(1)
    
    # Send stop request to daemon
    # Note: Uses env/stop endpoint (likely should be policy/stop)
    r = requests.post(f"{daemon_url(port)}/env/stop/{policy_id}", params={"env_id": policy_id})
    
    if r.status_code != 200:
        print(f"[red]Error:[/red] {r.json()['detail']}")
        raise typer.Exit(1)
    
    # Confirm successful stop
    print(f"[green]Policy {policy_id} stopped[/green]")