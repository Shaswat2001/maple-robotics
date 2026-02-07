"""
Serve commands for the MAPLE CLI.

This module provides commands for starting the MAPLE daemon and serving
policy and environment containers. The daemon orchestrates all container
management and provides the API for running evaluations.

Commands:
- serve (root): Start the MAPLE daemon
- policy: Serve a policy model in a container
- env: Serve an environment in a container

The daemon can run in the foreground (blocking) or be detached to run in
the background as a separate process.
"""

import json
import typer 
import shutil
import requests
import subprocess
from rich import print
from typing import Optional, Dict, Any
from maple.utils.config import get_config
from maple.server.daemon import VLADaemon
from maple.utils.misc import daemon_url, parse_error_response, load_kwargs

# Create the serve sub-application
# no_args_is_help=False allows running without subcommand to start daemon
# invoke_without_command=True enables the callback to run when no subcommand given
serve_app = typer.Typer(no_args_is_help=False, invoke_without_command=True)

@serve_app.callback()
def serve_root(
    ctx: typer.Context,
    port: int = typer.Option(None, "--port"),
    device: str = typer.Option(None, "--device"),
    detach: bool = typer.Option(False, "--detach")
) -> None:
    """
    Start the MAPLE daemon.
    
    Launches the MAPLE daemon which manages policy and environment containers
    and provides the API for running evaluations. Can run in foreground
    (blocking) mode or detached as a background process.
    
    When detached, the daemon runs in a new session and logs to /tmp/vla.out
    and /tmp/vla.err.
    
    :param ctx: Typer context for checking if subcommand was invoked.
    :param port: Port number for the daemon to listen on.
    :param device: Default device for policy containers (e.g., 'cuda:0', 'cpu').
    :param detach: If True, run daemon in background as separate process.
    """
    config = get_config()
    # If a subcommand was invoked (policy/env), don't start daemon
    if ctx.invoked_subcommand is not None:
        return
    
    # Use config defaults for unspecified parameters
    port = port or config.daemon.port
    device = device or config.policy.default_device
    
    if detach:
        # Detached mode - run daemon in background
        
        # Find the 'vla' executable in PATH
        vla_bin = shutil.which("vla")
        if vla_bin is None:
            print("[red]Could not find 'vla' executable in PATH[/red]")
            raise typer.Exit(1)
        
        # Start daemon as a background process with new session
        # start_new_session=True ensures daemon survives terminal closure
        subprocess.Popen(
            [
                vla_bin,
                "serve",
                "--port",
                str(port),
                "--device",
                device,
            ],
            stdout=open("/tmp/vla.out", "a"),  # Redirect stdout to log file
            stderr=open("/tmp/vla.err", "a"),  # Redirect stderr to log file
            start_new_session=True,  # Detach from current session
        )
        print("[green]MAPLE daemon started in background[/green]")
        return
    
    # Foreground mode - run daemon blocking
    daemon = VLADaemon(port=port, device=device)
    daemon.start()

@serve_app.command("policy")
def serve_policy(
    name: str = typer.Argument(..., help="name (e.g., openvla:latest)"),
    port: int = typer.Option(None, "--port"),
    device: str = typer.Option(None, "--device", "-d"),
    host_port: Optional[int] = typer.Option(None, "--host-port", "-p", help="Bind to specific port"),
    model_load_kwargs: str = typer.Option(None, "--mdl-kwargs", "-m", help="Model-specific loading parameters")
) -> None:
    """
    Serve a policy model in a container.
    
    Requests the daemon to start a policy container with the specified model.
    The policy is loaded onto the specified device and made available via
    HTTP API for inference requests.
    
    :param name: Policy specification string (name or name:version).
    :param port: Daemon port number.
    :param device: Device to load policy on (e.g., 'cuda:0', 'cpu').
    :param host_port: Optional specific port to bind the policy container to.
    :param model_load_kwargs: Model-specific loading parameters.
    """
    
    config = get_config()
    # Use config defaults for unspecified parameters
    port = port or config.daemon.port
    device = device or config.policy.default_device
    model_load_kwargs = load_kwargs(model_load_kwargs)    
    model_load_kwargs = model_load_kwargs or config.policy.model_load_kwargs

    # Build request payload with policy configuration
    payload = {"spec": name, "device": device, "model_load_kwargs": model_load_kwargs}
    
    # Add optional host port if specified
    if host_port is not None:
        payload["host_port"] = host_port
    
    # Send serve request to daemon
    r = requests.post(f"{daemon_url(port)}/policy/serve", json=payload)
    
    if r.status_code != 200:
        print(f"[red]Error:[/red] {parse_error_response(r)}")
        raise typer.Exit(1)
    
    # Display serving confirmation with container details
    data = r.json()
    print(f"[green]✓ Serving policy:[/green] {name}")
    print(f"  Policy ID: {data.get('policy_id')}")
    print(f"  Port: http://localhost:{data.get('port')}")
    print(f"  Device: {data.get('device')}")
    print(f"  Parameters : ")
    for key, val in model_load_kwargs.items():
        print(f"    {key} : {val}")

@serve_app.command("env")
def serve_env(
    name: str = typer.Argument(..., help="name (e.g., libero)"),
    port: int = typer.Option(None, "--port"),
    num_envs: int = typer.Option(None, "--num-envs", min=1),
    host_port: Optional[int] = typer.Option(None, "--host-port", "-p", help="Bind to specific port (only with num_envs=1)")
) -> None:
    """
    Serve an environment in a container.
    
    Requests the daemon to start one or more environment containers with
    the specified environment backend. Multiple instances can be created
    for parallel evaluation.
    
    :param name: Environment name or image specification.
    :param port: Daemon port number.
    :param num_envs: Number of environment instances to create.
    :param host_port: Optional specific port (only valid when num_envs=1).
    """

    config = get_config()
    # Use config defaults for unspecified parameters
    port = port or config.daemon.port
    num_envs = num_envs if num_envs is not None else config.env.default_num_envs
    
    # Build request payload with environment configuration
    payload = {"name": name, "num_envs": num_envs}
    
    # Add optional host port if specified
    # Note: Only valid when num_envs=1
    if host_port is not None:
        payload["host_port"] = host_port
    
    # Send serve request to daemon
    r = requests.post(
        f"{daemon_url(port)}/env/serve",
        json=payload
    )

    if r.status_code != 200:
        print(f"[red]Error:[/red] {parse_error_response(r)}")
        raise typer.Exit(1)
    
    # Display serving confirmation with environment IDs
    data = r.json()
    print(f"[green]✓ Serving env:[/green] {name} ({data['num_envs']} instance(s))")
    
    # List all created environment instance IDs
    for env_id in data.get("env_ids", []):
        print(f"  • {env_id}")