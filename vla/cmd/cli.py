import typer 
import shutil
import requests
import subprocess
from typing import Tuple
from rich import print
from vla.server.daemon import VLADaemon

def daemon_url(port: int):
    return f"http://127.0.0.1:{port}"

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

serve_app = typer.Typer(no_args_is_help=False, invoke_without_command=True)
app.add_typer(serve_app, name="serve")

@serve_app.callback()
def serve_root(ctx: typer.Context,
               port: int = typer.Option(8080, "--port"),
               device: str = typer.Option("cuda:0", "--device"),
               detach: bool = typer.Option(False, "--detach")):
    
    if ctx.invoked_subcommand is not None:
        return
    
    if detach:
        vla_bin = shutil.which("vla")
        if vla_bin is None:
            print("[red]Could not find 'vla' executable in PATH[/red]")
            raise typer.Exit(1)

        subprocess.Popen(
            [
                vla_bin,
                "serve",
                "--port",
                str(port),
                "--device",
                device,
            ],
            stdout=open("/tmp/vla.out", "a"),
            stderr=open("/tmp/vla.err", "a"),
            start_new_session=True,  # important
        )

        print("[green]VLA daemon started in background[/green]")
        return

    
    daemon = VLADaemon(port=port, device=device)
    daemon.start()

@serve_app.command("policy")
def serve_policy(name: str,
                 port: int = typer.Option(8080, "--port")):
    
    r = requests.post(f"{daemon_url(port)}/policy/serve", json={"spec": name})
    
    if r.status_code != 200:
        print(f"[red]Error:[/red] {r.json()['detail']}")
        raise typer.Exit(1)

    print(f"[bold cyan]SERVE POLICY[/bold cyan] name={name}")

@serve_app.command("env")
def serve_env(name: str,
              port: int = typer.Option(8080, "--port"),
              num_envs: int = typer.Option(1, "--num-envs", min=1),
              headless: bool = typer.Option(True, "--headless/--gui")):
    
    requests.post(f"{daemon_url(port)}/env/serve", params={"name": name, "num_envs": num_envs})
    print(f"[bold cyan]SERVE ENV[/bold cyan] name={name} num_envs={num_envs} headless={headless}")

list_app = typer.Typer(no_args_is_help=True)
app.add_typer(list_app, name="list")

@list_app.command("policy")
def list_policy(port: int = typer.Option(8080, "--port")):
    r = requests.get(f"{daemon_url(port)}/policy/list")
    print("[yellow]Policies:[/yellow]", r.json()["policies"])

@list_app.command("env")
def list_env(port: int = typer.Option(8080, "--port")):
    r = requests.get(f"{daemon_url(port)}/env/list")
    print("[yellow]Policies:[/yellow]", r.json()["envs"])

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
        r = requests.get(f"http://127.0.0.1:{port}/status", timeout=1)
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


