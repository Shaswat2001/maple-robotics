"""
Doctor command for MAPLE CLI.

This module provides diagnostic commands for checking system health,
verifying dependencies, and troubleshooting common issues. It helps
users quickly identify and resolve configuration problems.

Checks performed:
- Docker daemon availability and permissions
- GPU/CUDA availability and driver version
- Disk space for images and data
- Port availability for daemon
- MAPLE daemon status
- Container health
- Network connectivity
"""

import os
import sys
import shutil
import socket
import subprocess
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Any

import typer
from rich import print
from rich.table import Table
from rich.panel import Panel
from rich.console import Console

from maple.utils.config import get_config
from maple.utils.lock import is_daemon_running
from maple.state import store

console = Console()

# Create the doctor sub-application
doctor_app = typer.Typer(no_args_is_help=False, invoke_without_command=True)


class DiagnosticResult:
    """Result of a single diagnostic check."""
    
    def __init__(
        self, 
        name: str, 
        passed: bool, 
        message: str, 
        details: Optional[str] = None,
        fix: Optional[str] = None
    ):
        self.name = name
        self.passed = passed
        self.message = message
        self.details = details
        self.fix = fix
    
    def __repr__(self):
        status = "✓" if self.passed else "✗"
        return f"{status} {self.name}: {self.message}"


def check_docker() -> DiagnosticResult:
    """Check if Docker is installed and accessible."""
    # Check if docker command exists
    docker_path = shutil.which("docker")
    if not docker_path:
        return DiagnosticResult(
            name="Docker Installation",
            passed=False,
            message="Docker not found in PATH",
            fix="Install Docker: https://docs.docker.com/get-docker/"
        )
    
    # Check if docker daemon is running and accessible
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode != 0:
            stderr = result.stderr.lower()
            
            if "permission denied" in stderr:
                return DiagnosticResult(
                    name="Docker Permissions",
                    passed=False,
                    message="Permission denied accessing Docker socket",
                    details=result.stderr.strip(),
                    fix="Run: sudo usermod -aG docker $USER && newgrp docker"
                )
            elif "cannot connect" in stderr or "is the docker daemon running" in stderr:
                return DiagnosticResult(
                    name="Docker Daemon",
                    passed=False,
                    message="Docker daemon is not running",
                    details=result.stderr.strip(),
                    fix="Start Docker: sudo systemctl start docker"
                )
            else:
                return DiagnosticResult(
                    name="Docker",
                    passed=False,
                    message="Docker error",
                    details=result.stderr.strip()
                )
        
        # Parse docker version
        version_result = subprocess.run(
            ["docker", "version", "--format", "{{.Server.Version}}"],
            capture_output=True,
            text=True,
            timeout=5
        )
        version = version_result.stdout.strip() if version_result.returncode == 0 else "unknown"
        
        return DiagnosticResult(
            name="Docker",
            passed=True,
            message=f"Docker is running (v{version})"
        )
        
    except subprocess.TimeoutExpired:
        return DiagnosticResult(
            name="Docker",
            passed=False,
            message="Docker command timed out",
            fix="Check if Docker daemon is responding: docker ps"
        )
    except Exception as e:
        return DiagnosticResult(
            name="Docker",
            passed=False,
            message=f"Error checking Docker: {e}"
        )


def check_nvidia_docker() -> DiagnosticResult:
    """Check if NVIDIA Container Toolkit is installed."""
    try:
        result = subprocess.run(
            ["docker", "run", "--rm", "--gpus", "all", "nvidia/cuda:11.0-base", "nvidia-smi", "-L"],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode == 0:
            gpu_count = len([l for l in result.stdout.strip().split("\n") if l.startswith("GPU")])
            return DiagnosticResult(
                name="NVIDIA Docker",
                passed=True,
                message=f"NVIDIA Container Toolkit working ({gpu_count} GPU(s) available)"
            )
        else:
            if "could not select device driver" in result.stderr.lower():
                return DiagnosticResult(
                    name="NVIDIA Docker",
                    passed=False,
                    message="NVIDIA Container Toolkit not installed",
                    fix="Install: https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html"
                )
            return DiagnosticResult(
                name="NVIDIA Docker",
                passed=False,
                message="GPU containers not working",
                details=result.stderr.strip()[:200]
            )
    except subprocess.TimeoutExpired:
        return DiagnosticResult(
            name="NVIDIA Docker",
            passed=False,
            message="GPU check timed out (may be pulling image)",
            details="Try running: docker run --rm --gpus all nvidia/cuda:11.0-base nvidia-smi"
        )
    except Exception as e:
        return DiagnosticResult(
            name="NVIDIA Docker",
            passed=False,
            message=f"Error: {e}"
        )


def check_gpu() -> DiagnosticResult:
    """Check GPU availability and driver version."""
    nvidia_smi = shutil.which("nvidia-smi")
    
    if not nvidia_smi:
        return DiagnosticResult(
            name="GPU",
            passed=False,
            message="nvidia-smi not found - no NVIDIA GPU or drivers not installed",
            fix="Install NVIDIA drivers: https://www.nvidia.com/Download/index.aspx"
        )
    
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,driver_version,memory.total", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            gpus = result.stdout.strip().split("\n")
            gpu_info = gpus[0].split(", ") if gpus else ["Unknown", "Unknown", "Unknown"]
            return DiagnosticResult(
                name="GPU",
                passed=True,
                message=f"{gpu_info[0]} (Driver: {gpu_info[1]}, Memory: {gpu_info[2]})",
                details=f"{len(gpus)} GPU(s) detected"
            )
        else:
            return DiagnosticResult(
                name="GPU",
                passed=False,
                message="nvidia-smi failed",
                details=result.stderr.strip()
            )
    except Exception as e:
        return DiagnosticResult(
            name="GPU",
            passed=False,
            message=f"Error checking GPU: {e}"
        )


def check_disk_space() -> DiagnosticResult:
    """Check available disk space."""
    home = Path.home()
    maple_dir = home / ".maple"
    
    try:
        # Get disk usage for home directory
        stat = os.statvfs(home)
        free_gb = (stat.f_frsize * stat.f_bavail) / (1024**3)
        total_gb = (stat.f_frsize * stat.f_blocks) / (1024**3)
        used_pct = ((total_gb - free_gb) / total_gb) * 100
        
        # Check MAPLE directory size if it exists
        maple_size_gb = 0
        if maple_dir.exists():
            maple_size = sum(f.stat().st_size for f in maple_dir.rglob("*") if f.is_file())
            maple_size_gb = maple_size / (1024**3)
        
        if free_gb < 10:
            return DiagnosticResult(
                name="Disk Space",
                passed=False,
                message=f"Low disk space: {free_gb:.1f} GB free",
                details=f"MAPLE using {maple_size_gb:.1f} GB",
                fix="Free up disk space or expand storage"
            )
        elif free_gb < 50:
            return DiagnosticResult(
                name="Disk Space",
                passed=True,
                message=f"{free_gb:.1f} GB free (warning: VLA models need 20-50GB each)",
                details=f"MAPLE using {maple_size_gb:.1f} GB"
            )
        else:
            return DiagnosticResult(
                name="Disk Space",
                passed=True,
                message=f"{free_gb:.1f} GB free ({used_pct:.0f}% used)",
                details=f"MAPLE using {maple_size_gb:.1f} GB"
            )
    except Exception as e:
        return DiagnosticResult(
            name="Disk Space",
            passed=False,
            message=f"Error checking disk: {e}"
        )


def check_port(port: int) -> DiagnosticResult:
    """Check if the daemon port is available."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('localhost', port))
        sock.close()
        
        if result == 0:
            # Port is in use - check if it's MAPLE daemon
            if is_daemon_running(port):
                return DiagnosticResult(
                    name=f"Port {port}",
                    passed=True,
                    message=f"MAPLE daemon is running on port {port}"
                )
            else:
                return DiagnosticResult(
                    name=f"Port {port}",
                    passed=False,
                    message=f"Port {port} is in use by another process",
                    fix=f"Use a different port: maple serve --port <other_port>"
                )
        else:
            return DiagnosticResult(
                name=f"Port {port}",
                passed=True,
                message=f"Port {port} is available"
            )
    except Exception as e:
        return DiagnosticResult(
            name=f"Port {port}",
            passed=False,
            message=f"Error checking port: {e}"
        )


def check_daemon() -> DiagnosticResult:
    """Check if MAPLE daemon is running and healthy."""
    config = get_config()
    port = config.daemon.port
    
    if is_daemon_running(port):
        try:
            import requests
            r = requests.get(f"http://localhost:{port}/health", timeout=5)
            if r.status_code == 200:
                data = r.json()
                policies = data.get("policies", 0)
                envs = data.get("envs", 0)
                return DiagnosticResult(
                    name="MAPLE Daemon",
                    passed=True,
                    message=f"Running on port {port}",
                    details=f"{policies} policies, {envs} environments serving"
                )
            else:
                return DiagnosticResult(
                    name="MAPLE Daemon",
                    passed=False,
                    message=f"Daemon unhealthy (status {r.status_code})"
                )
        except Exception as e:
            return DiagnosticResult(
                name="MAPLE Daemon",
                passed=False,
                message=f"Daemon not responding: {e}"
            )
    else:
        return DiagnosticResult(
            name="MAPLE Daemon",
            passed=True,
            message="Not running (start with: maple serve)"
        )


def check_state_db() -> DiagnosticResult:
    """Check MAPLE state database."""
    try:
        policies = store.list_policies()
        envs = store.list_envs()
        containers = store.list_containers()
        
        return DiagnosticResult(
            name="State Database",
            passed=True,
            message=f"{len(policies)} policies, {len(envs)} envs pulled",
            details=f"{len(containers)} container records"
        )
    except Exception as e:
        return DiagnosticResult(
            name="State Database",
            passed=False,
            message=f"Database error: {e}",
            fix="Try: rm ~/.maple/state.db (will lose pull history)"
        )


def check_python() -> DiagnosticResult:
    """Check Python version."""
    version = sys.version_info
    version_str = f"{version.major}.{version.minor}.{version.micro}"
    
    if version.major < 3 or (version.major == 3 and version.minor < 9):
        return DiagnosticResult(
            name="Python",
            passed=False,
            message=f"Python {version_str} (requires 3.9+)",
            fix="Upgrade Python to 3.9 or higher"
        )
    else:
        return DiagnosticResult(
            name="Python",
            passed=True,
            message=f"Python {version_str}"
        )


@doctor_app.callback(invoke_without_command=True)
def doctor(
    ctx: typer.Context,
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed output"),
    skip_gpu: bool = typer.Option(False, "--skip-gpu", help="Skip GPU checks (faster)"),
) -> None:
    """
    Run system diagnostics.
    
    Checks system configuration, dependencies, and common issues.
    Provides actionable fixes for any problems found.
    """
    if ctx.invoked_subcommand is not None:
        return
    
    config = get_config()
    
    print(Panel.fit("[bold cyan]MAPLE System Diagnostics[/bold cyan]"))
    print()
    
    results: List[DiagnosticResult] = []
    
    # Run checks
    with console.status("[bold green]Checking Python..."):
        results.append(check_python())
    
    with console.status("[bold green]Checking Docker..."):
        results.append(check_docker())
    
    if not skip_gpu:
        with console.status("[bold green]Checking GPU..."):
            results.append(check_gpu())
        
        # Only check nvidia-docker if docker is working
        if results[1].passed:
            with console.status("[bold green]Checking NVIDIA Docker (may take a moment)..."):
                results.append(check_nvidia_docker())
    
    with console.status("[bold green]Checking disk space..."):
        results.append(check_disk_space())
    
    with console.status("[bold green]Checking port availability..."):
        results.append(check_port(config.daemon.port))
    
    with console.status("[bold green]Checking daemon status..."):
        results.append(check_daemon())
    
    with console.status("[bold green]Checking state database..."):
        results.append(check_state_db())
    
    # Display results
    print()
    
    passed = 0
    failed = 0
    
    for result in results:
        if result.passed:
            passed += 1
            print(f"[green]✓[/green] [bold]{result.name}[/bold]: {result.message}")
        else:
            failed += 1
            print(f"[red]✗[/red] [bold]{result.name}[/bold]: {result.message}")
        
        if verbose and result.details:
            print(f"  [dim]{result.details}[/dim]")
        
        if result.fix:
            print(f"  [yellow]Fix:[/yellow] {result.fix}")
    
    # Summary
    print()
    if failed == 0:
        print(f"[bold green]All {passed} checks passed![/bold green]")
    else:
        print(f"[bold yellow]{passed} passed, {failed} failed[/bold yellow]")
        print()
        print("[dim]Run with --verbose for more details[/dim]")


@doctor_app.command("containers")
def doctor_containers() -> None:
    """Check health of all running containers."""
    try:
        import docker
        client = docker.from_env()
    except Exception as e:
        print(f"[red]Cannot connect to Docker: {e}[/red]")
        raise typer.Exit(1)
    
    # Get MAPLE containers
    containers = store.list_containers()
    
    if not containers:
        print("[yellow]No MAPLE containers registered[/yellow]")
        return
    
    table = Table(title="Container Health")
    table.add_column("ID", style="cyan")
    table.add_column("Name")
    table.add_column("Type")
    table.add_column("Status")
    table.add_column("Health")
    
    for record in containers:
        container_id = record.get("id", "")[:12]
        name = record.get("name", "unknown")
        ctype = record.get("type", "unknown")
        
        try:
            container = client.containers.get(record["id"])
            status = container.status
            
            # Check health
            health = "N/A"
            if status == "running":
                health_status = container.attrs.get("State", {}).get("Health", {}).get("Status")
                if health_status:
                    health = health_status
                else:
                    health = "[green]running[/green]"
            elif status == "exited":
                health = "[red]exited[/red]"
            else:
                health = f"[yellow]{status}[/yellow]"
            
            table.add_row(container_id, name, ctype, status, health)
            
        except docker.errors.NotFound:
            table.add_row(container_id, name, ctype, "[red]not found[/red]", "[red]missing[/red]")
        except Exception as e:
            table.add_row(container_id, name, ctype, "[red]error[/red]", str(e)[:20])
    
    console.print(table)
