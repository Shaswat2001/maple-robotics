import typer 
import requests
from rich import print
from vla.cmd.cli.misc import daemon_url

list_app = typer.Typer(no_args_is_help=True)


@list_app.command("policy")
def list_policy(port: int = typer.Option(8080, "--port")):
    r = requests.get(f"{daemon_url(port)}/policy/list")
    print("[yellow]Policies:[/yellow]", r.json()["policies"])

@list_app.command("env")
def list_env(port: int = typer.Option(8080, "--port")):
    r = requests.get(f"{daemon_url(port)}/env/list")
    print("[yellow]Policies:[/yellow]", r.json()["envs"])

