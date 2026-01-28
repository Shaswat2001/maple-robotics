import typer 
import requests
from rich import print
from typing import Tuple
from vla.cmd.cli.misc import daemon_url
from vla.cmd.cli import pull_app, serve_app, list_app, env_app

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

app.add_typer(pull_app, name="pull")
app.add_typer(serve_app, name="serve")
app.add_typer(list_app, name="list")
app.add_typer(env_app, name="env")
# ---------- ENV ----------

@app.command("run")
def run(
    spec: str = typer.Argument(..., help="POLICY@ENV (example: openvla@libero)"),
    task: str = typer.Option(..., "--task"),
    instruction: str = typer.Option("", "--instruction"),
    port: int = typer.Option(8080, "--port"),
):
    
    if "@" not in spec:
        raise typer.BadParameter("Expected POLICY@ENV")

    policy, env = parse_policy_env(spec)
    r = requests.post(
        f"{daemon_url(port)}/run",
        json={
            "policy": policy,
            "env": env,
            "task": task,
            "instruction": instruction,
        },
    )

    if r.status_code != 200:
        print(f"[red]Error:[/red] {r.json()['detail']}")
        raise typer.Exit(1)

    result = r.json()
    print("[bold green]RUN COMPLETE[/bold green]")
    print(result)

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


