import yaml
import typer 
from rich import print
from maple.config import config, CONFIG_FILE

config_app = typer.Typer(no_args_is_help=True)

@config_app.command("show")
def config_show():
    """Show current configuration"""

    print("[cyan]Current configuration:[/cyan]\n")
    print(yaml.dump(config.to_dict(), default_flow_style=False, sort_keys=False))

@config_app.command("init")
def config_init(force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing config")):
    """Create default config file"""
    
    if CONFIG_FILE.exists() and not force:
        print(f"[yellow]Config already exists:[/yellow] {CONFIG_FILE}")
        print("Use --force to overwrite")
        return
    
    config.save(CONFIG_FILE)
    print(f"[green]✓ Config created:[/green] {CONFIG_FILE}")

@config_app.command("path")
def config_path():
    """Show config file path"""
    print(CONFIG_FILE)