"""
Sync commands for the MAPLE CLI.

This module provides commands for synchronizing the database with the actual
state of the filesystem and Docker. This is useful when users manually delete
resources (model weights, Docker images) outside of the MAPLE CLI.

Commands:
- all: Sync both policies and environments
- policies: Sync policy database with filesystem
- envs: Sync environment database with Docker images
"""

import typer
import docker
from rich import print
from rich.table import Table
from pathlib import Path

from maple.utils.logging import get_logger
from maple.state.store import (
    list_policies, 
    list_envs, 
    remove_policy, 
    remove_env,
)

log = get_logger("sync")

# Create the sync sub-application
sync_app = typer.Typer(no_args_is_help=True)

@sync_app.command("policies")
def sync_policies(
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be removed without doing it"),
) -> None:
    """
    Sync policy database with filesystem.
    
    Scans the database for policies and checks if their model weights still exist
    on disk. Removes database entries for policies whose weights have been deleted.
    
    :param dry_run: If True, only show what would be removed without actually removing.
    """
    print("[cyan]Scanning policies...[/cyan]\n")
    
    policies = list_policies()
    
    if not policies:
        print("[yellow]No policies found in database[/yellow]")
        return
    
    missing_policies = []
    
    # Check each policy
    for policy in policies:
        name = policy['name']
        version = policy['version']
        path = Path(policy['path'])
        
        if not path.exists():
            missing_policies.append(policy)
    
    if not missing_policies:
        print("[green]✓ All policies in database have weights on disk[/green]")
        return
    
    # Display missing policies
    print(f"[yellow]Found {len(missing_policies)} policies with missing weights:[/yellow]\n")
    
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Name")
    table.add_column("Version")
    table.add_column("Path")
    table.add_column("Status")
    
    for policy in missing_policies:
        table.add_row(
            policy['name'],
            policy['version'],
            str(policy['path']),
            "[red]Missing[/red]"
        )
    
    print(table)
    print()
    
    if dry_run:
        print("[yellow]Dry run - no changes made[/yellow]")
        return

    # Remove missing policies from database
    removed_count = 0
    for policy in missing_policies:
        name = policy['name']
        version = policy['version']
        
        if remove_policy(name, version):
            removed_count += 1
            print(f"[green]✓[/green] Removed {name}:{version}")
        else:
            print(f"[red]✗[/red] Failed to remove {name}:{version}")
    
    print(f"\n[bold green]✓ Sync complete: Removed {removed_count} policy entries[/bold green]")

@sync_app.command("envs")
def sync_envs(
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be removed without doing it"),
) -> None:
    """
    Sync environment database with Docker images.
    
    Scans the database for environments and checks if their Docker images still exist.
    Removes database entries for environments whose images have been deleted.

    :param dry_run: If True, only show what would be removed without actually removing.
    """
    print("[cyan]Scanning environments...[/cyan]\n")
    
    envs = list_envs()
    
    if not envs:
        print("[yellow]No environments found in database[/yellow]")
        return
    
    # Get Docker client
    try:
        client = docker.from_env()
    except Exception as e:
        print(f"[red]Error connecting to Docker:[/red] {e}")
        raise typer.Exit(1)
    
    # Get list of all Docker images
    try:
        docker_images = {img.tags[0] for img in client.images.list() if img.tags}
    except Exception as e:
        print(f"[red]Error listing Docker images:[/red] {e}")
        raise typer.Exit(1)
    
    missing_envs = []
    
    # Check each environment
    for env in envs:
        name = env['name']
        image = env['image']
        
        if image not in docker_images:
            missing_envs.append(env)
    
    if not missing_envs:
        print("[green]✓ All environments in database have Docker images[/green]")
        return
    
    # Display missing environments
    print(f"[yellow]Found {len(missing_envs)} environments with missing Docker images:[/yellow]\n")
    
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Name")
    table.add_column("Image")
    table.add_column("Status")
    
    for env in missing_envs:
        table.add_row(
            env['name'],
            env['image'],
            "[red]Missing[/red]"
        )
    
    print(table)
    print()
    
    if dry_run:
        print("[yellow]Dry run - no changes made[/yellow]")
        return
    
    # Remove missing environments from database
    removed_count = 0
    for env in missing_envs:
        name = env['name']
        
        if remove_env(name):
            removed_count += 1
            print(f"[green]✓[/green] Removed {name}")
        else:
            print(f"[red]✗[/red] Failed to remove {name}")
    
    print(f"\n[bold green]✓ Sync complete: Removed {removed_count} environment entries[/bold green]")

@sync_app.command("all")
def sync_all(
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be removed without doing it"),
) -> None:
    """
    Sync both policies and environments.
    
    Runs both policy and environment sync operations in sequence. This is a
    convenience command for checking and cleaning up both resource types at once.
    
    :param dry_run: If True, only show what would be removed without actually removing.
    """
    print("[bold cyan]Starting full sync...[/bold cyan]\n")
    
    # Sync policies
    print("[bold]1. Syncing Policies[/bold]")
    print("-" * 50)
    sync_policies(dry_run=dry_run)
    
    print("\n")
    
    # Sync environments
    print("[bold]2. Syncing Environments[/bold]")
    print("-" * 50)
    sync_envs(dry_run=dry_run)
    
    print("\n[bold green]✓ Full sync complete[/bold green]")