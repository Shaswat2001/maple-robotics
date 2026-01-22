import os
import sys
import time
import signal
import threading
from rich import print
from pathlib import Path

import uvicorn
from fastapi import FastAPI

from vla.state.store import load_state

PID_FILE = Path.home() / ".vla" / "deamon.pid"

class VLADaemon:

    def __init__(self, port: int, device: str):
        self.running = True
        self.port = port
        self.device = device 
        self.state = load_state()

        self.app = FastAPI(title= "VLA Daemon")

        @self.app.get("/status")
        def status():
            return {
                "running": True,
                "port": self.port,
                "device": self.device,
                "state": self.state
            }
    
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

        signal.signal(signal.SIGINT, self._shutdown)
        signal.signal(signal.SIGTERM, self._shutdown)

        thread = threading.Thread(target=self._run_api, daemon=True)
        thread.start()

        self._loop()

    def _run_api(self):
        uvicorn.run(
            self.app,
            host="127.0.0.1",
            port=self.port,
            log_level="error",
        )

    def _loop(self):
        while self.running:
            time.sleep(1)

    def _shutdown(self, *_):
        print("\n[yellow]Shutting down VLA daemon[/yellow]")
        self.running = False
        if PID_FILE.exists():
            PID_FILE.unlink()
        sys.exit(0)

