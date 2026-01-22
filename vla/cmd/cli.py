from __future__ import annotations

import re
import typer 
from typing import Tuple
from rich import print
from vla.state.store import load_state, save_state
from vla.server.daemon import VLADaemon

app = typer.Typer(no_args_is_help= True)

def parse_policy_env(spec: str) -> Tuple[str, str]:
    """
    Parses 'policy@env' shorthand. Example: 'openvla@libero'
    """

    if "@" not in spec:
        raise typer.BadParameter("Expected POLICY@ENV (example: openvla@libero)")
    
    policy, env = spec.split("@", 1)
    policy, env = policy.strip(), env.strip()
    if not policy or not env:
        raise typer.BadParameter("Invalid POLICY@ENV")
    return policy, env

pull_app = typer.Typer(no_args_is_help=True)
app.add_typer(pull_app, name="pull")

@pull_app.command("policy")
def pull_policy(name: str):
    state = load_state()
    if name not in state["policies"]:
        state["policies"].append(name)
        save_state(state)
    print(f"[bold green]PULL POLICY[/bold green] name={name}")

@pull_app.command("env")
def pull_env(name: str):
    state = load_state()
    if name not in state["envs"]:
        state["envs"].append(name)
        save_state(state)
    print(f"[bold green]PULL ENV[/bold green] name={name}")

serve_app = typer.Typer(no_args_is_help=False)
app.add_typer(serve_app, name="serve")

@serve_app.callback(invoke_without_command=True)
def serve_root(port: int = typer.Option(8080, "--port"),
               device: str = typer.Option("cuda:0", "--device")):
    
    daemon = VLADaemon(port=port, device=device)
    daemon.start()

@serve_app.command("policy")
def serve_policy(name: str,
                 device: str = typer.Option("cuda:0", "--device")):
    
    state = load_state()
    if name not in state["policies"]:
        raise typer.BadParameter(f"Policy '{name}' not pulled")

    if name not in state["served_policies"]:
        state["served_policies"].append(name)
        save_state(state)

    print(f"[bold cyan]SERVE POLICY[/bold cyan] name={name} device={device}")

@serve_app.command("env")
def serve_env(name: str,
              num_envs: int = typer.Option(1, "--num-envs", min=1),
              headless: bool = typer.Option(True, "--headless/--gui")):
    
    state = load_state()
    if name not in state["envs"]:
        raise typer.BadParameter(f"Env '{name}' not pulled")

    if name not in state["served_envs"]:
        state["served_envs"].append(name)
        save_state(state)

    print(f"[bold cyan]SERVE ENV[/bold cyan] name={name} num_envs={num_envs} headless={headless}")

list_app = typer.Typer(no_args_is_help=True)
app.add_typer(list_app, name="list")

@list_app.command("policy")
def list_policy():
    state = load_state()
    print("[yellow]Policies:[/yellow]", sorted(state["policies"]))

@list_app.command("env")
def list_env():
    state = load_state()
    print("[yellow]Envs:[/yellow]", sorted(state["envs"]))

@app.command("run")
def run(
    spec: str = typer.Argument(..., help="POLICY@ENV (example: openvla@libero)"),
    task: str = typer.Option(..., "--task"),
    instruction: str = typer.Option("", "--instruction"),
    max_steps: int = typer.Option(200, "--max-steps", min=1),
    record_video: bool = typer.Option(True, "--video/--no-video"),
):
    policy, env = parse_policy_env(spec)
    print(
        f"[bold magenta]RUN[/bold magenta] policy={policy} env={env} task={task} "
        f"max_steps={max_steps} video={record_video}"
    )
    if instruction:
        print(f"[dim]instruction:[/dim] {instruction}")


def main():
    app()

if __name__ == "__main__":
    main()


