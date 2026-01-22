import os
import sys
import time
import signal
import threading
from rich import print
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException

from vla.state.store import load_state, save_state

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
        
        @self.app.get("/policy/list")
        def policies():
            return {"policies": self.state["policies"]}

        @self.app.get("/env/list")
        def envs():
            return {"envs": self.state["envs"]}
        
        @self.app.get("/policy/pull")
        def pull_policies(name: str):
            if name not in self.state["policies"]:
                self.state["policies"].append(name)
                save_state(self.state)
            return {"ok": True, "policy": name}

        @self.app.get("/env/pull")
        def pull_envs(name: str):

            if name not in self.state["envs"]:
                self.state["envs"].append(name)
                save_state(self.state)
            return {"ok": True, "env": name}
        
        @self.app.get("/policy/serve")
        def serve_policies(name: str):
            if name not in self.state["policies"]:
                raise HTTPException(status_code=400, detail="Policy not pulled")
            if name not in self.state.setdefault("served_policies", []):
                self.state["served_policies"].append(name)
                save_state(self.state)
            return {"served": name}
        
        @self.app.get("/env/serve")
        def serve_envs(name: str):
            if name not in self.state["envs"]:
                raise HTTPException(status_code=400, detail="Env not pulled")
            if name not in self.state.setdefault("served_envs", []):
                self.state["served_envs"].append(name)
                save_state(self.state)
            return {"served": name}
        
        @self.app.get("/stop")
        def stop():
            self._shutdown()
            return {"stopped": True}
    
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

