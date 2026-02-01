import typer 
import requests
from rich import print
from maple.cmd.cli.misc import daemon_url

pull_app = typer.Typer(no_args_is_help=True)

@pull_app.command("policy")
def pull_policy(name: str, port: int = typer.Option(8080, "--port")):
    r = requests.post(f"{daemon_url(port)}/policy/pull", json={"spec": name})

    if r.status_code != 200:
        print(f"[red]Error:[/red] {r.json()['detail']}")
        raise typer.Exit(1)
    
    print(f"[green]PULLED policy[/green] {name}")

@pull_app.command("env")
def pull_env(name: str, port: int = typer.Option(8080, "--port")):
    requests.post(f"{daemon_url(port)}/env/pull", params={"name": name})
    print(f"[bold green]PULL ENV[/bold green] name={name}")

