"""
Environment management commands for the MAPLE CLI.

This module provides commands for interacting with running environment
containers. It allows users to setup tasks, reset environments, step through
episodes, query environment information, list available tasks, and stop
environment containers.

Commands:
- setup: Initialize an environment with a specific task
- reset: Reset an environment to its initial state
- step: Execute a single action step in the environment
- info: Display information about an environment
- tasks: List available tasks for an environment backend
- stop: Stop one or all environment containers
"""

import typer 
import requests
from rich import print
from typing import List, Optional
from maple.utils.config import config
from maple.cmd.cli.misc import daemon_url

# Create the env sub-application
# no_args_is_help=True ensures help is shown when no command is given
env_app = typer.Typer(no_args_is_help=True)

@env_app.command("setup")
def setup_env(
    port: int = typer.Option(None, "--port"),
    env_id: str = typer.Option(None, "--id", help="Environment ID"),
    task: str = typer.Option(None, "--task", "-t", help="Task spec (e.g., libero_10/0)"),
    seed: int = typer.Option(None, "--seed", "-s")
) -> None:
    """
    Initialize an environment with a specific task.
    
    Sets up an environment container to run a particular task. This includes
    loading the task specification, applying the random seed if provided, and
    preparing the environment for episode execution.
    
    :param port: Daemon port number.
    :param env_id: Identifier of the environment container.
    :param task: Task specification string.
    :param seed: Optional random seed for environment initialization.
    """
    # Use config default if port not specified
    port = port or config.daemon.port

    # Validate required parameters
    if env_id is None or task is None:
        print(f"[red]Error: environment id or task is None[/red]")
        raise typer.Exit(1)
    
    # Build request payload with required fields
    payload = {"env_id": env_id, "task": task}
    # Add optional seed if provided
    if seed is not None:
        payload["seed"] = seed
    
    # Send setup request to daemon
    r = requests.post(f"{daemon_url(port)}/env/setup", json=payload)
    if r.status_code != 200:
        print(f"[red]Error:[/red] {r.json().get('detail', 'Unknown error')}")
        raise typer.Exit(1)
    
    # Display setup confirmation with task details
    data = r.json()
    print(f"[green]✓ Environment setup[/green]")
    print(f"  Task: {data.get('task')}")
    print(f"  Instruction: {data.get('instruction')}")

@env_app.command("reset")
def reset_env(
    port: int = typer.Option(None, "--port"),
    env_id: str = typer.Option(None, "--id", help="Environment ID"),
    seed: int = typer.Option(None, "--seed", "-s")
) -> None:
    """
    Reset an environment to its initial state.
    
    Resets the environment to the beginning of the current task, returning
    the initial observation. Optionally applies a new random seed.
    
    :param port: Daemon port number.
    :param env_id: Identifier of the environment container.
    :param seed: Optional random seed for reset.
    """
    # Use config default if port not specified
    port = port or config.daemon.port

    # Validate required parameter
    if env_id is None:
        print(f"[red]Error: environment id is None[/red]")
        raise typer.Exit(1)
    
    # Build request payload
    payload = {"env_id": env_id}
    # Add optional seed if provided
    if seed is not None:
        payload["seed"] = seed
    
    # Send reset request to daemon
    r = requests.post(f"{daemon_url(port)}/env/reset", json=payload)
    if r.status_code != 200:
        print(f"[red]Error:[/red] {r.json().get('detail', 'Unknown error')}")
        raise typer.Exit(1)
    
    # Display reset confirmation with observation info
    data = r.json()
    print(f"[green]✓ Environment reset[/green]")
    
    # Show available observation keys for debugging/info
    obs = data.get("observation", {})
    print(f"  Observation keys: {list(obs.keys())}")

@env_app.command("step")
def step_env(
    env_id: str = typer.Option(None, "--id", help="Environment ID"),
    action: List[float] = typer.Option(..., "--action", "-a", help="Action values"),
    port: int = typer.Option(None, "--port")
) -> None:
    """
    Execute a single action step in the environment.
    
    Sends an action to the environment and receives the resulting observation,
    reward, termination status, and truncation status. Used for manual stepping
    through episodes or testing environment responses.
    
    :param env_id: Identifier of the environment container.
    :param action: List of action values to execute.
    :param port: Daemon port number.
    """
    # Use config default if port not specified
    port = port or config.daemon.port

    # Validate required parameter
    if env_id is None:
        print(f"[red]Error: environment id is None[/red]")
        raise typer.Exit(1)
    
    # Send step request with action to daemon
    # Convert action to list to ensure proper JSON serialization
    r = requests.post(
        f"{daemon_url(port)}/env/step",
        json={"env_id": env_id, "action": list(action)}
    )
    
    if r.status_code != 200:
        print(f"[red]Error:[/red] {r.json().get('detail', 'Unknown error')}")
        raise typer.Exit(1)
    
    # Display step results
    data = r.json()
    print(f"[cyan]Step result:[/cyan]")
    print(f"  Reward: {data.get('reward', 0):.4f}")
    print(f"  Terminated: {data.get('terminated', False)}")
    print(f"  Truncated: {data.get('truncated', False)}")

@env_app.command("info")
def env_info(
    port: int = typer.Option(None, "--port"),
    env_id: str = typer.Option(None, "--id", help="Environment ID")
) -> None:
    """
    Display information about an environment.
    
    Retrieves and displays metadata about a running environment container,
    including the current task, suite, instruction, and action space details.
    
    :param port: Daemon port number.
    :param env_id: Identifier of the environment container.
    """
    # Use config default if port not specified
    port = port or config.daemon.port
    
    # Request environment info from daemon
    r = requests.get(f"{daemon_url(port)}/env/info/{env_id}")
    
    if r.status_code != 200:
        print(f"[red]Error:[/red] {r.json().get('detail', 'Unknown error')}")
        raise typer.Exit(1)
    
    # Display environment metadata
    data = r.json()
    print(f"[cyan]Environment Info:[/cyan]")
    print(f"  Task: {data.get('task')}")
    print(f"  Suite: {data.get('suite')}")
    print(f"  Instruction: {data.get('instruction')}")
    
    # Show action space if available
    if "action_space" in data:
        print(f"  Action space: {data['action_space']}")

@env_app.command("tasks")
def env_tasks(
    backend: str = typer.Argument("libero", help="Environment backend name"),
    suite: Optional[str] = typer.Option(None, "--suite", "-s", help="Filter by suite"),
    port: int = typer.Option(None, "--port")
) -> None:
    """
    List available tasks for an environment backend.
    
    Queries the daemon for all available tasks in the specified environment
    backend. Can optionally filter to a specific task suite. Displays task
    indices, names, and instructions for each suite.
    
    :param backend: Name of the environment backend to query.
    :param suite: Optional suite name to filter results.
    :param port: Daemon port number.
    """
    # Use config default if port not specified
    port = port or config.daemon.port

    # Build query parameters
    params = {}
    if suite:
        params["suite"] = suite
    
    # Request task list from daemon
    r = requests.get(f"{daemon_url(port)}/env/tasks/{backend}", params=params)
    
    if r.status_code != 200:
        print(f"[red]Error:[/red] {r.json().get('detail', 'Unknown error')}")
        raise typer.Exit(1)
    
    data = r.json()
    
    # Display tasks grouped by suite
    for suite_name, tasks in data.items():
        # Skip internal/metadata keys
        if suite_name.startswith("_"):
            continue
        
        print(f"\n[yellow]{suite_name}[/yellow]")
        
        # Handle error responses for specific suites
        if isinstance(tasks, dict) and "error" in tasks:
            print(f"  [red]Error: {tasks['error']}[/red]")
        # Handle suite metadata/description format
        elif isinstance(tasks, dict) and "description" in tasks:
            print(f"  {tasks.get('description', '')} ({tasks.get('count', '?')} tasks)")
        # Handle detailed task list format
        elif isinstance(tasks, list):
            # Show first 10 tasks to avoid overwhelming output
            for t in tasks[:10]:
                print(f"  [{t.get('index', '?')}] {t.get('name', 'unknown')}")
                # Show instruction if available
                if t.get("instruction"):
                    print(f"      → {t['instruction']}")
            # Indicate if there are more tasks
            if len(tasks) > 10:
                print(f"  ... and {len(tasks) - 10} more")

@env_app.command("stop")
def stop_env(
    port: int = typer.Option(None, "--port"),
    env_id: str = typer.Option(None, "--id", help="Environment ID")
) -> None:
    """
    Stop one or all environment containers.
    
    Stops environment containers managed by the daemon. If env_id is provided,
    stops only that specific environment. If env_id is None, stops all running
    environment containers.
    
    :param port: Daemon port number.
    :param env_id: Optional identifier of specific environment to stop.
    """
    # Use config default if port not specified
    port = port or config.daemon.port
    
    if env_id is None:
        # Stop all environment containers
        r = requests.post(f"{daemon_url(port)}/env/stop")
        
        if r.status_code != 200:
            print(f"[red]Error:[/red] {r.json()['detail']}")
            raise typer.Exit(1)
        
        print("[green]All env stopped[/green]")
    else:
        # Stop specific environment container
        r = requests.post(f"{daemon_url(port)}/env/stop/{env_id}", params={"env_id": env_id})

        if r.status_code != 200:
            print(f"[red]Error:[/red] {r.json()['detail']}")
            raise typer.Exit(1)
        
        print(f"[green]Env {env_id} stopped[/green]")