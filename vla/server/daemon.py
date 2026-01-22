import os
import sys
import time
import signal
from rich import print
from pathlib import Path

from vla.state.store import load_state

PID_FILE = Path.home() / ".vla" / "deamon.pid"

class VLADaemon:

    def __init__(self, port: int, device: str):
        self.running = True
        self.port = port
        self.device = device 
    
    def start(self):
        
        if PID_FILE.exists():
            print("[red]Deamon already running[/red]")
            sys.exit(1)

        PID_FILE.parent.mkdir(parents=True, exist_ok=True)
        PID_FILE.write_text(str(os.getpid()))

        print(
        f"[bold cyan]VLA daemon started[/bold cyan] "
        f"(port={self.port}, device={self.device})"
        )

        state = load_state()
        print("[dim]Loaded state:[/dim]", state)

        signal.signal(signal.SIGINT, self._shutdown)
        signal.signal(signal.SIGTERM, self._shutdown)

        self._loop()

    def _loop(self):
        while self.running:
            time.sleep(1)

    def _shutdown(self, *_):
        print("\n[yellow]Shutting down VLA daemon[/yellow]")
        self.running = False
        if PID_FILE.exists():
            PID_FILE.unlink()
        sys.exit(0)

