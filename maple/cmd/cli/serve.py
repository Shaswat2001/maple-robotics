import typer 
import shutil
import requests
import subprocess
from rich import print
from typing import Optional
from maple.config import config
from maple.server.daemon import VLADaemon
from maple.cmd.cli.misc import daemon_url

serve_app = typer.Typer(no_args_is_help=False, invoke_without_command=True)

@serve_app.callback()
def serve_root(ctx: typer.Context,
               port: int = typer.Option(None, "--port"),
               device: str = typer.Option(None, "--device"),
               detach: bool = typer.Option(False, "--detach")):
    
    if ctx.invoked_subcommand is not None:
        return
    
    port = port or config.daemon.port
    device = device or config.policy.default_device
    
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

        print("[green]MAPLE daemon started in background[/green]")
        return

    
    daemon = VLADaemon(port=port, device=device)
    daemon.start()

@serve_app.command("policy")
def serve_policy(name: str,
                 port: int = typer.Option(None, "--port"),
                 device: str = typer.Option(None, "--device", "-d"),
                 host_port: Optional[int] = typer.Option(None, "--host-port", "-p", help="Bind to specific port"),
                 attn: str = typer.Option(None, "--attn", "-a", help="Attention: flash_attention_2, sdpa, eager")):
    
    port = port or config.daemon.port
    device = device or config.policy.default_device
    attn = attn or config.policy.attn_implementation

    payload = {"spec": name, "device": device, "attn_implementation": attn}
    if host_port is not None:
        payload["host_port"] = host_port
    
    r = requests.post(f"{daemon_url(port)}/policy/serve", json=payload)
    
    if r.status_code != 200:
        print(f"[red]Error:[/red] {r.json()['detail']}")
        raise typer.Exit(1)
    
    data = r.json()
    print(f"[green]✓ Serving policy:[/green] {name}")
    print(f"  Policy ID: {data.get('policy_id')}")
    print(f"  Port: http://localhost:{data.get('port')}")
    print(f"  Device: {data.get('device')}")
    print(f"  Attention: {data.get('attn_implementation')}")

@serve_app.command("env")
def serve_env(name: str,
              port: int = typer.Option(None, "--port"),
              num_envs: int = typer.Option(None, "--num-envs", min=1),
              host_port: Optional[int] = typer.Option(None, "--host-port", "-p", help="Bind to specific port (only with num_envs=1)")):
    
    port = port or config.daemon.port
    num_envs = num_envs if num_envs is not None else config.env.default_num_envs
    
    payload = {"name": name, "num_envs": num_envs}
    if host_port is not None:
        payload["host_port"] = host_port
    
    r = requests.post(
        f"{daemon_url(port)}/env/serve",
        json=payload
    )

    if r.status_code != 200:
        print(f"[red]Error:[/red] {r.json().get('detail', 'Unknown error')}")
        raise typer.Exit(1)
    
    data = r.json()
    print(f"[green] Serving env:[/green] {name} ({data['num_envs']} instance(s))")
    for env_id in data.get("env_ids", []):
        print(f"  • {env_id}")