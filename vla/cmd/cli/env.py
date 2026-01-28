import typer 
import requests
from rich import print
from vla.cmd.cli.misc import daemon_url

env_app = typer.Typer(no_args_is_help=True)

@env_app.command("stop")
def stop_env(port: int = typer.Option(8080, "--port"), env_id: str = typer.Option(None, "--id")):

    if env_id is None:
        requests.post(f"{daemon_url(port)}/env/stop")
        print("[green]All env stopped[/green]")
    else:
        requests.post(f"{daemon_url(port)}/env/stop/{env_id}",params={"env_id": env_id})
        print(f"[green]Env {env_id} stopped[/green]")

@env_app.command("setup")
def setup_env(port: int = typer.Option(8080, "--port")):
    pass

