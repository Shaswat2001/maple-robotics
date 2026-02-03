import typer 
import requests
from rich import print
from maple.config import config
from maple.cmd.cli.misc import daemon_url

policy_app = typer.Typer(no_args_is_help=True)

@policy_app.command("info")
def policy_info(port: int = typer.Option(None, "--port"), policy_id: str = typer.Option(None, "--id",help="Policy ID")):

    port = port or config.daemon.port
    r = requests.get(f"{daemon_url(port)}/policy/info/{policy_id}")
    
    if r.status_code != 200:
        print(f"[red]Error:[/red] {r.json().get('detail', 'Unknown error')}")
        raise typer.Exit(1)
    
    data = r.json()
    print(f"[cyan]Policy Info:[/cyan]")
    print(f"  Input: {data.get('inputs')}")
    print(f"  Output: {data.get('outputs')}")
    print(f"  Version: {data.get('versions')}")

@policy_app.command("stop")
def stop_env(port: int = typer.Option(None, "--port"), policy_id: str = typer.Option(None, "--id",help="Policy ID")):

    port = port or config.daemon.port
    if policy_id is None:
        print(f"[red]Error: Policy id is None[/red]")
        raise typer.Exit(1)
    
    r = requests.post(f"{daemon_url(port)}/env/stop/{policy_id}",params={"env_id": policy_id})

    if r.status_code != 200:
        print(f"[red]Error:[/red] {r.json()['detail']}")
        raise typer.Exit(1)
    
    print(f"[green]Policy {policy_id} stopped[/green]")