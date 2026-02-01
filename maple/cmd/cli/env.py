import typer 
import requests
from rich import print
from typing import List, Optional
from maple.cmd.cli.misc import daemon_url

env_app = typer.Typer(no_args_is_help=True)

@env_app.command("setup")
def setup_env(port: int = typer.Option(8080, "--port"),
              env_id: str = typer.Option(None, "--id", help="Environment ID"),
              task: str = typer.Option(None, "--task", "-t", help="Task spec (e.g., libero_10/0)"),
              seed: int = typer.Option(None, "--seed", "-s")):
    

    if env_id is None or task is None:
        print(f"[red]Error: environment id or task is None[/red]")
        raise typer.Exit(1)
    
    payload = {"env_id": env_id, "task": task}
    if seed is not None:
        payload["seed"] = seed
    
    r = requests.post(f"{daemon_url(port)}/env/setup", json=payload)
    if r.status_code != 200:
        print(f"[red]Error:[/red] {r.json().get('detail', 'Unknown error')}")
        raise typer.Exit(1)
    
    data = r.json()
    print(f"[green]✓ Environment setup[/green]")
    print(f"  Task: {data.get('task')}")
    print(f"  Instruction: {data.get('instruction')}")

@env_app.command("reset")
def reset_env(port: int = typer.Option(8080, "--port"),
              env_id: str = typer.Option(None, "--id", help="Environment ID"),
              seed: int = typer.Option(None, "--seed", "-s")):
    
    if env_id is None:
        print(f"[red]Error: environment id is None[/red]")
        raise typer.Exit(1)
    
    payload = {"env_id": env_id}
    if seed is not None:
        payload["seed"] = seed
    
    r = requests.post(f"{daemon_url(port)}/env/reset", json=payload)
    if r.status_code != 200:
        print(f"[red]Error:[/red] {r.json().get('detail', 'Unknown error')}")
        raise typer.Exit(1)
    
    data = r.json()
    print(f"[green]✓ Environment reset[/green]")
    
    # Show observation keys
    obs = data.get("observation", {})
    print(f"  Observation keys: {list(obs.keys())}")

@env_app.command("step")
def step_env(env_id: str = typer.Option(None, "--id", help="Environment ID"),
             action: List[float] = typer.Option(..., "--action", "-a", help="Action values"),
             port: int = typer.Option(8080, "--port")):
    
    if env_id is None:
        print(f"[red]Error: environment id is None[/red]")
        raise typer.Exit(1)
    
    r = requests.post(
        f"{daemon_url(port)}/env/step",
        json={"env_id": env_id, "action": list(action)}
    )
    
    if r.status_code != 200:
        print(f"[red]Error:[/red] {r.json().get('detail', 'Unknown error')}")
        raise typer.Exit(1)
    
    data = r.json()
    print(f"[cyan]Step result:[/cyan]")
    print(f"  Reward: {data.get('reward', 0):.4f}")
    print(f"  Terminated: {data.get('terminated', False)}")
    print(f"  Truncated: {data.get('truncated', False)}")

@env_app.command("info")
def env_info(port: int = typer.Option(8080, "--port"), env_id: str = typer.Option(None, "--id",help="Environment ID")):

    r = requests.get(f"{daemon_url(port)}/env/info/{env_id}")
    
    if r.status_code != 200:
        print(f"[red]Error:[/red] {r.json().get('detail', 'Unknown error')}")
        raise typer.Exit(1)
    
    data = r.json()
    print(f"[cyan]Environment Info:[/cyan]")
    print(f"  Task: {data.get('task')}")
    print(f"  Suite: {data.get('suite')}")
    print(f"  Instruction: {data.get('instruction')}")
    
    if "action_space" in data:
        print(f"  Action space: {data['action_space']}")

@env_app.command("tasks")
def env_tasks(backend: str = typer.Argument("libero", help="Environment backend name"),
              suite: Optional[str] = typer.Option(None, "--suite", "-s", help="Filter by suite"),
              port: int = typer.Option(8080, "--port")):
    """List available tasks for an environment"""
    params = {}
    if suite:
        params["suite"] = suite
    
    r = requests.get(f"{daemon_url(port)}/env/tasks/{backend}", params=params)
    
    if r.status_code != 200:
        print(f"[red]Error:[/red] {r.json().get('detail', 'Unknown error')}")
        raise typer.Exit(1)
    
    data = r.json()
    
    for suite_name, tasks in data.items():
        if suite_name.startswith("_"):
            continue
        
        print(f"\n[yellow]{suite_name}[/yellow]")
        
        if isinstance(tasks, dict) and "error" in tasks:
            print(f"  [red]Error: {tasks['error']}[/red]")
        elif isinstance(tasks, dict) and "description" in tasks:
            print(f"  {tasks.get('description', '')} ({tasks.get('count', '?')} tasks)")
        elif isinstance(tasks, list):
            for t in tasks[:10]:  # Show first 10
                print(f"  [{t.get('index', '?')}] {t.get('name', 'unknown')}")
                if t.get("instruction"):
                    print(f"      → {t['instruction']}")
            if len(tasks) > 10:
                print(f"  ... and {len(tasks) - 10} more")

@env_app.command("stop")
def stop_env(port: int = typer.Option(8080, "--port"), env_id: str = typer.Option(None, "--id",help="Environment ID")):

    if env_id is None:
        r = requests.post(f"{daemon_url(port)}/env/stop")
        
        if r.status_code != 200:
            print(f"[red]Error:[/red] {r.json()['detail']}")
            raise typer.Exit(1)
        
        print("[green]All env stopped[/green]")
    else:
        r = requests.post(f"{daemon_url(port)}/env/stop/{env_id}",params={"env_id": env_id})

        if r.status_code != 200:
            print(f"[red]Error:[/red] {r.json()['detail']}")
            raise typer.Exit(1)
        
        print(f"[green]Env {env_id} stopped[/green]")