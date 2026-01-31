import typer 
import requests
from rich import print
from typing import Optional
from vla.cmd.cli.misc import daemon_url, parse_policy_env
from vla.cmd.cli import pull_app, serve_app, list_app, env_app

app = typer.Typer(no_args_is_help= True)

app.add_typer(pull_app, name="pull")
app.add_typer(serve_app, name="serve")
app.add_typer(list_app, name="list")
app.add_typer(env_app, name="env")

@app.command("run")
def run(
    policy_id: str = typer.Argument(..., help="Policy ID (e.g., openvla-7b-a1b2c3d4)"),
    env_id: str = typer.Argument(..., help="Environment ID (e.g., libero-x1y2z3w4)"),
    task: str = typer.Option(..., "--task", "-t", help="Task spec (e.g., libero_10/0)"),
    instruction: Optional[str] = typer.Option(None, "--instruction", "-i", help="Override task instruction"),
    max_steps: int = typer.Option(300, "--max-steps", "-m", help="Maximum steps per episode"),
    seed: Optional[int] = typer.Option(None, "--seed", "-s", help="Random seed"),
    unnorm_key: Optional[str] = typer.Option(None, "--unnorm-key", "-u", help="Dataset key for action unnormalization"),
    save_video: bool = typer.Option(False, "--save-video", "-v", help="Save rollout video"),
    video_path: Optional[str] = typer.Option(None, "--video-path", help="Custom video output path"),
    port: int = typer.Option(8080, "--port"),
):
    """
    Run a policy on an environment task.
    
    Example:
        vla run openvla-7b-abc123 libero-xyz789 --task libero_10/0
    """
    payload = {
        "policy_id": policy_id,
        "env_id": env_id,
        "task": task,
        "max_steps": max_steps,
        "save_video": save_video,
    }
    
    if instruction:
        payload["instruction"] = instruction
    if seed is not None:
        payload["seed"] = seed
    if unnorm_key:
        payload["unnorm_key"] = unnorm_key
    if video_path:
        payload["video_path"] = video_path
    
    print(f"[cyan]Running policy on task...[/cyan]")
    print(f"  Policy: {policy_id}")
    print(f"  Env: {env_id}")
    print(f"  Task: {task}")
    print(f"  Max steps: {max_steps}")
    
    try:
        r = requests.post(
            f"{daemon_url(port)}/run",
            json=payload,
            timeout=max_steps * 300,  # Generous timeout
        )
    except requests.exceptions.Timeout:
        print(f"[red]Error:[/red] Request timed out after {max_steps * 300}s")
        raise typer.Exit(1)

    if r.status_code != 200:
        print(f"[red]Error:[/red] {r.json().get('detail', 'Unknown error')}")
        raise typer.Exit(1)

    result = r.json()
    
    # Display results
    success = result.get("success", False)
    if success:
        print(f"\n[bold green]✓ Task completed successfully![/bold green]")
    else:
        print(f"\n[yellow]Task finished (not successful)[/yellow]")
    
    print(f"\n[cyan]Results:[/cyan]")
    print(f"  Run ID: {result.get('run_id')}")
    print(f"  Steps: {result.get('steps')}")
    print(f"  Total Reward: {result.get('total_reward', 0):.4f}")
    print(f"  Terminated: {result.get('terminated')}")
    print(f"  Truncated: {result.get('truncated')}")
    
    if result.get("video_path"):
        print(f"  Video saved: {result.get('video_path')}")

@app.command("status")
def status(port: int = typer.Option(8080, "--port")):
    try:
        r = requests.get(f"http://0.0.0.0:{port}/status", timeout=1)
        data = r.json()
        print("[bold green]VLA daemon running[/bold green]")
        print(data)
    except requests.exceptions.ConnectionError:
        print("[red]VLA daemon not running[/red]")

@app.command("stop")
def stop(
    port: int = typer.Option(8080, "--port"),
):
    try:
        requests.post(f"{daemon_url(port)}/stop")
        print("[green]VLA daemon stopped[/green]")
    except requests.exceptions.ConnectionError:
        print("[red]Daemon not running[/red]")

def main():
    app()

if __name__ == "__main__":
    main()


