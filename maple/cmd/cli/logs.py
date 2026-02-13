"""
Logs command for MAPLE CLI.

This module provides easy access to container logs for debugging.
Users can view logs from policy and environment containers without
needing to know Docker container IDs.

Commands:
- logs <id>: View logs for a specific policy or environment
- logs daemon: View MAPLE daemon logs
- logs list: List all available log sources
"""

import os
import sys
import subprocess
from pathlib import Path
from typing import Optional

import typer
from rich import print
from rich.table import Table
from rich.console import Console
from rich.syntax import Syntax

from maple.utils.config import get_config
from maple.state import store

console = Console()

# Create the logs sub-application
logs_app = typer.Typer(no_args_is_help=True)


def get_container_id_by_maple_id(maple_id: str) -> Optional[str]:
    """
    Look up Docker container ID from MAPLE policy/env ID.
    
    :param maple_id: MAPLE-assigned ID (e.g., 'openvla-7b-a1b2c3d4')
    :return: Docker container ID or None if not found
    """
    containers = store.list_containers()
    
    for container in containers:
        # Match by MAPLE ID or partial Docker container ID
        if container.get("name", "").startswith(maple_id) or \
           container.get("id", "").startswith(maple_id) or \
           maple_id in container.get("name", ""):
            return container.get("id")
    
    return None


def stream_docker_logs(container_id: str, follow: bool = False, tail: int = 100) -> None:
    """
    Stream logs from a Docker container.
    
    :param container_id: Docker container ID
    :param follow: If True, follow log output (like tail -f)
    :param tail: Number of lines to show from end
    """
    cmd = ["docker", "logs"]
    
    if follow:
        cmd.append("-f")
    
    if tail:
        cmd.extend(["--tail", str(tail)])
    
    cmd.append(container_id)
    
    try:
        if follow:
            # Stream logs interactively
            process = subprocess.Popen(cmd, stdout=sys.stdout, stderr=sys.stderr)
            try:
                process.wait()
            except KeyboardInterrupt:
                process.terminate()
                print("\n[dim]Log streaming stopped[/dim]")
        else:
            # Get logs and display
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                print(f"[red]Error:[/red] {result.stderr}")
                raise typer.Exit(1)
            
            if result.stdout:
                print(result.stdout)
            if result.stderr:
                # Docker logs often go to stderr
                print(result.stderr)
                
    except FileNotFoundError:
        print("[red]Error: docker command not found[/red]")
        raise typer.Exit(1)


@logs_app.command("show")
def logs_show(
    container_id: str = typer.Argument(..., help="Policy/Env ID or Docker container ID"),
    follow: bool = typer.Option(False, "--follow", "-f", help="Follow log output"),
    tail: int = typer.Option(100, "--tail", "-n", help="Number of lines to show"),
) -> None:
    """
    View logs for a policy or environment container.
    
    Examples:
        maple logs show openvla-7b-a1b2c3
        maple logs show libero-x1y2z3w4 -f
        maple logs show abc123def456 --tail 50
    """
    # Try to resolve MAPLE ID to Docker container ID
    docker_id = get_container_id_by_maple_id(container_id)
    
    if docker_id:
        print(f"[dim]Container: {docker_id[:12]}[/dim]")
        stream_docker_logs(docker_id, follow=follow, tail=tail)
    else:
        # Try using the ID directly as Docker container ID
        try:
            stream_docker_logs(container_id, follow=follow, tail=tail)
        except Exception:
            print(f"[red]Container not found: {container_id}[/red]")
            print("\nUse [cyan]maple logs list[/cyan] to see available containers")
            raise typer.Exit(1)


@logs_app.command("daemon")
def logs_daemon(
    follow: bool = typer.Option(False, "--follow", "-f", help="Follow log output"),
    tail: int = typer.Option(100, "--tail", "-n", help="Number of lines to show"),
    errors: bool = typer.Option(False, "--errors", "-e", help="Show only errors (stderr)"),
) -> None:
    """
    View MAPLE daemon logs.
    
    Shows logs from /tmp/vla.out and /tmp/vla.err when running in detached mode.
    """
    stdout_log = Path("/tmp/vla.out")
    stderr_log = Path("/tmp/vla.err")
    
    if not stdout_log.exists() and not stderr_log.exists():
        print("[yellow]No daemon logs found[/yellow]")
        print("[dim]Logs are only created when running with --detach[/dim]")
        print("[dim]If running in foreground, logs appear in the terminal[/dim]")
        return
    
    if follow:
        # Use tail -f to follow logs
        log_file = stderr_log if errors else stdout_log
        if not log_file.exists():
            print(f"[yellow]Log file not found: {log_file}[/yellow]")
            return
        
        print(f"[dim]Following {log_file}... (Ctrl+C to stop)[/dim]")
        try:
            subprocess.run(["tail", "-f", str(log_file)])
        except KeyboardInterrupt:
            print("\n[dim]Stopped following logs[/dim]")
        except FileNotFoundError:
            # Fallback if tail not available
            with open(log_file, "r") as f:
                # Move to end
                f.seek(0, 2)
                while True:
                    line = f.readline()
                    if line:
                        print(line, end="")
                    else:
                        import time
                        time.sleep(0.1)
    else:
        # Show recent logs
        if errors:
            files = [stderr_log] if stderr_log.exists() else []
        else:
            files = [f for f in [stdout_log, stderr_log] if f.exists()]
        
        for log_file in files:
            if log_file == stderr_log:
                print("[bold red]═══ Errors (stderr) ═══[/bold red]")
            else:
                print("[bold cyan]═══ Output (stdout) ═══[/bold cyan]")
            
            try:
                with open(log_file, "r") as f:
                    lines = f.readlines()
                    for line in lines[-tail:]:
                        print(line, end="")
            except Exception as e:
                print(f"[red]Error reading {log_file}: {e}[/red]")
        
        if not files:
            print("[yellow]No log files found[/yellow]")


@logs_app.command("list")
def logs_list() -> None:
    """
    List all available log sources.
    
    Shows all running containers and their IDs for use with 'maple logs show'.
    """
    # List MAPLE containers
    containers = store.list_containers()
    
    if containers:
        table = Table(title="Container Logs")
        table.add_column("MAPLE ID", style="cyan")
        table.add_column("Type")
        table.add_column("Docker ID", style="dim")
        table.add_column("Command")
        
        for container in containers:
            maple_id = container.get("name", "unknown")
            ctype = container.get("type", "unknown")
            docker_id = container.get("id", "")[:12]
            cmd = f"maple logs show {maple_id}"
            
            table.add_row(maple_id, ctype, docker_id, cmd)
        
        console.print(table)
    else:
        print("[yellow]No MAPLE containers registered[/yellow]")
    
    # Check for daemon logs
    print()
    print("[bold]Daemon Logs:[/bold]")
    
    stdout_log = Path("/tmp/vla.out")
    stderr_log = Path("/tmp/vla.err")
    
    if stdout_log.exists() or stderr_log.exists():
        if stdout_log.exists():
            size = stdout_log.stat().st_size / 1024
            print(f"  [green]✓[/green] stdout: {stdout_log} ({size:.1f} KB)")
        if stderr_log.exists():
            size = stderr_log.stat().st_size / 1024
            print(f"  [green]✓[/green] stderr: {stderr_log} ({size:.1f} KB)")
        print(f"  [dim]View with: maple logs daemon[/dim]")
    else:
        print("  [dim]No daemon logs (running in foreground or not started)[/dim]")


@logs_app.command("clear")
def logs_clear(
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
) -> None:
    """
    Clear daemon log files.
    """
    stdout_log = Path("/tmp/vla.out")
    stderr_log = Path("/tmp/vla.err")
    
    files = [f for f in [stdout_log, stderr_log] if f.exists()]
    
    if not files:
        print("[yellow]No log files to clear[/yellow]")
        return
    
    if not force:
        confirm = typer.confirm(f"Clear {len(files)} log file(s)?")
        if not confirm:
            print("[dim]Cancelled[/dim]")
            return
    
    for log_file in files:
        try:
            log_file.unlink()
            print(f"[green]✓[/green] Cleared {log_file}")
        except Exception as e:
            print(f"[red]Error clearing {log_file}: {e}[/red]")


# Default command when running 'maple logs <id>'
@logs_app.callback(invoke_without_command=True)
def logs_default(
    ctx: typer.Context,
    container_id: Optional[str] = typer.Argument(None, help="Policy/Env ID to show logs for"),
    follow: bool = typer.Option(False, "--follow", "-f", help="Follow log output"),
    tail: int = typer.Option(100, "--tail", "-n", help="Number of lines to show"),
) -> None:
    """
    View container logs.
    
    Quick access to policy and environment container logs.
    
    Examples:
        maple logs openvla-7b-a1b2c3
        maple logs libero-x1y2z3w4 -f
    """
    if ctx.invoked_subcommand is not None:
        return
    
    if container_id:
        # Direct shortcut: maple logs <id>
        logs_show(container_id, follow=follow, tail=tail)
    else:
        # No args, show help
        print("[yellow]Usage: maple logs <container_id>[/yellow]")
        print()
        print("Use [cyan]maple logs list[/cyan] to see available containers")
        print("Use [cyan]maple logs daemon[/cyan] to view daemon logs")
