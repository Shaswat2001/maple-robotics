"""
Remove commands for the MAPLE CLI.

This module provides commands for removing (deleting) policies and environments
from the system. This includes:
- Removing entries from the database
- Deleting model weights from disk
- Removing Docker images

Commands:
- policy: Remove a policy model and its weights
- env: Remove an environment and its Docker image
"""

import typer
import docker
import shutil
import requests
from rich import print
from pathlib import Path

from maple.utils.config import get_config
from maple.utils.logging import get_logger
from maple.utils.misc import daemon_url
from maple.utils.spec import parse_versioned
from maple.state.store import remove_policy, remove_env, get_policy, get_env

log = get_logger("remove")

# Create the remove sub-application
remove_app = typer.Typer(no_args_is_help=True)

@remove_app.command("policy")
def remove_policy_cmd(
    name: str = typer.Argument(..., help="Policy name (e.g., openvla:7b)"),
    port: int = typer.Option(None, "--port"),
    keep_weights: bool = typer.Option(False, "--keep-weights", help="Keep model weights on disk"),
) -> None:
    """
    Remove a policy model from the system.
    
    This command will:
    1. Remove the policy from the database
    2. Delete model weights from disk (unless --keep-weights is specified)
    3. Stop any running containers using this policy
    
    :param name: Name of the policy model to remove.
    :param version: Version identifier of the policy.
    :param port: Daemon port number.
    :param keep_weights: If True, keep the model weights on disk.
    """
    config = get_config()
    port = port or config.daemon.port
    name, version = parse_versioned(name)
    # Check if policy exists
    policy = get_policy(name, version)
    if not policy:
        print(f"[red]Error:[/red] Policy {name}:{version} not found in database")
        raise typer.Exit(1)
    
    image_name = policy['image']
    # Get policy path
    weights_path = Path(policy['path'])
    
    # Show what will be deleted
    print(f"\n[yellow]The following will be removed:[/yellow]")
    print(f"  Policy: {name}:{version}")
    print(f"  Database entry: Yes")
    print(f"  Weights path: {weights_path}")
    print(f"  Docker image: {image_name}")
    print(f"  Delete weights: {'No (--keep-weights)' if keep_weights else 'Yes'}")
    
    try:
        # Get daemon status which includes serving policies
        r = requests.get(f"{daemon_url(port)}/status")
        if r.status_code == 200:
            status_data = r.json()
            serving_policies = status_data.get('serving', {}).get('policies', [])
            
            # Check if this policy is currently being served
            policy_key = f"{name}-{version}"
            matching_policies = [p for p in serving_policies if p.startswith(policy_key)]
            
            # Stop each matching policy container
            for policy_id in matching_policies:
                print(f"  Stopping policy container: {policy_id}")
                try:
                    requests.post(f"{daemon_url(port)}/policy/stop/{policy_id}")
                except Exception as e:
                    log.warning(f"Failed to stop policy {policy_id}: {e}")
    except Exception as e:
        log.warning(f"Could not check for running containers: {e}")
    
    # Remove from database
    removed = remove_policy(name, version)
    if removed:
        print(f"[green]✓[/green] Removed from database")
    else:
        print(f"[yellow]Warning:[/yellow] Policy not found in database")
    
    # Delete weights from disk
    if not keep_weights and weights_path.exists():
        try:
            if weights_path.is_dir():
                shutil.rmtree(weights_path)
            else:
                weights_path.unlink()
            print(f"[green]✓[/green] Deleted weights from {weights_path}")
        except Exception as e:
            print(f"[red]Error deleting weights:[/red] {e}")
            log.error(f"Failed to delete weights: {e}")
    elif not weights_path.exists():
        print(f"[yellow]Warning:[/yellow] Weights path does not exist: {weights_path}")

    try:
        client = docker.from_env()
        client.images.remove(image_name, force=True)
        print(f"[green]✓[/green] Removed Docker image: {image_name}")
    except docker.errors.ImageNotFound:
        print(f"[yellow]Warning:[/yellow] Docker image not found: {image_name}")
    except Exception as e:
        print(f"[red]Error removing Docker image:[/red] {e}")
        log.error(f"Failed to remove Docker image: {e}")
    
    print(f"\n[bold green]✓ Policy {name}:{version} removed successfully[/bold green]")

@remove_app.command("env")
def remove_env_cmd(
    name: str = typer.Argument(..., help="Environment name (e.g., libero)"),
    port: int = typer.Option(None, "--port"),
) -> None:
    """
    Remove an environment from the system.
    
    This command will:
    1. Remove the environment from the database
    2. Remove the Docker image (unless --keep-image is specified)
    3. Stop any running containers using this environment
    
    :param name: Name of the environment to remove.
    :param port: Daemon port number.
    """
    config = get_config()
    port = port or config.daemon.port
    
    # Check if environment exists
    env = get_env(name)
    if not env:
        print(f"[red]Error:[/red] Environment {name} not found in database")
        raise typer.Exit(1)
    
    image_name = env['image']
    
    # Show what will be deleted
    print(f"\n[yellow]The following will be removed:[/yellow]")
    print(f"  Environment: {name}")
    print(f"  Database entry: Yes")
    print(f"  Docker image: {image_name}")

    # Try to stop any running containers with this environment
    try:
        # Get daemon status which includes serving environments
        r = requests.get(f"{daemon_url(port)}/status")
        if r.status_code == 200:
            status_data = r.json()
            serving_envs = status_data.get('serving', {}).get('envs', [])
            
            # Check if this environment is currently being served
            matching_envs = [e for e in serving_envs if e.startswith(name)]
            
            # Stop each matching environment container
            for env_id in matching_envs:
                print(f"  Stopping environment container: {env_id}")
                try:
                    requests.post(f"{daemon_url(port)}/env/stop/{env_id}")
                except Exception as e:
                    log.warning(f"Failed to stop environment {env_id}: {e}")
    except Exception as e:
        log.warning(f"Could not check for running containers: {e}")
    
    # Remove from database
    removed = remove_env(name)
    if removed:
        print(f"[green]✓[/green] Removed from database")
    else:
        print(f"[yellow]Warning:[/yellow] Environment not found in database")
    
    # Remove Docker image
    try:
        client = docker.from_env()
        client.images.remove(image_name, force=True)
        print(f"[green]✓[/green] Removed Docker image: {image_name}")
    except docker.errors.ImageNotFound:
        print(f"[yellow]Warning:[/yellow] Docker image not found: {image_name}")
    except Exception as e:
        print(f"[red]Error removing Docker image:[/red] {e}")
        log.error(f"Failed to remove Docker image: {e}")

    print(f"\n[bold green]✓ Environment {name} removed successfully[/bold green]")