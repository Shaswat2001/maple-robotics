import os
import sys
import time
import uvicorn
import threading
from rich import print
from pathlib import Path
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException
from vla.state.store import load_state, save_state
from vla.schedular import Scheduler
from vla.utils.paths import policy_dir
from vla.utils.spec import parse_versioned
from vla.backend.policy.registry import POLICY_BACKENDS
from vla.backend.envs.registry import ENV_BACKENDS

PID_FILE = Path.home() / ".vla" / "deamon.pid"

class RunRequest(BaseModel):
    policy: str
    env: str
    task: str
    instruction: str | None = None

class PullPolicyRequest(BaseModel):
    spec: str  # e.g., "openvla:7b"

class ServePolicyRequest(BaseModel):
    spec: str  # e.g., "openvla:7b"

class VLADaemon:

    def __init__(self, port: int, device: str):
        self.running = True
        self.port = port
        self.device = device 
        self.state = load_state()

        self.schedular = Scheduler()

        self.shutdown_event = threading.Event()

        self.app = FastAPI(title= "VLA Daemon")

        @self.app.get("/status")
        def status():
            return {
                "running": True,
                "port": self.port,
                "device": self.device,
                "state": self.state
            }
        
        @self.app.post("/run")
        def run(req: RunRequest):
            
            if req.policy not in self.state.get("served_policies", {}):
                raise HTTPException(
                    status_code=400,
                    detail=f"Policy '{req.policy}' not served"
                )

            if req.env not in self.state.get("served_envs", {}):
                raise HTTPException(
                    status_code=400,
                    detail=f"Env '{req.env}' not served"
                )
            
            meta = self.scheduler.submit(req.dict())

            # --- dummy execution ---
            time.sleep(0.5)

            return {
                "run_id": meta["run_id"],
                "success": True,
                "policy": req.policy,
                "env": req.env,
                "task": req.task,
                "steps": 123,
                "reward": 0.92,
            }

        
        @self.app.get("/policy/list")
        def policies():
            return {"policies": self.state["policies"]}

        @self.app.get("/env/list")
        def envs():
            return {"envs": self.state["envs"]}
        
        @self.app.post("/policy/pull")
        def pull_policy(req: PullPolicyRequest):
            name, version = parse_versioned(req.spec)

            if name not in POLICY_BACKENDS:
                raise HTTPException(status_code=400, detail=f"Unknown policy backend '{name}'")

            backend = POLICY_BACKENDS[name]()

            dst = policy_dir(name, version)
            try:
                manifest = backend.pull(version=version, dst=dst)
            except Exception as e:
                raise HTTPException(status_code=400, detail=str(e))

            pulled = self.state.setdefault("policies", [])
            policy_id = f"{name}:{version}"
            if policy_id not in pulled:
                pulled.append(policy_id)

            # optional: store manifests
            self.state.setdefault("policy_manifests", {})[policy_id] = manifest
            save_state(self.state)

            return {"pulled": policy_id, "manifest": manifest}

        @self.app.post("/env/pull")
        def pull_envs(name: str):

            if name not in ENV_BACKENDS:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unknown env backend '{name}'"
                )

            if name not in self.state["envs"]:
                self.state["envs"].append(name)
                save_state(self.state)
            return {"env": name, "info": ENV_BACKENDS[name]().info()}
        
        @self.app.post("/policy/serve")
        def serve_policy(req: ServePolicyRequest):
            name, version = parse_versioned(req.spec)
            policy_id = f"{name}:{version}"

            if policy_id not in self.state.get("policies", []):
                raise HTTPException(status_code=400, detail=f"Policy '{policy_id}' not pulled")

            if name not in POLICY_BACKENDS:
                raise HTTPException(status_code=400, detail=f"Unknown policy backend '{name}'")

            backend = POLICY_BACKENDS[name]()
            model_path = policy_dir(name, version)

            # torch init stub happens here
            try:
                backend.load(version=version, model_path=model_path, device=self.device)
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Failed to load '{policy_id}': {e}")

            served = self.state.setdefault("served_policies", [])
            if policy_id not in served:
                served.append(policy_id)
                save_state(self.state)

            return {"served": policy_id}
        
        @self.app.post("/env/serve")
        def serve_envs(name: str):
            if name not in self.state["envs"]:
                raise HTTPException(status_code=400, detail="Env not pulled")
            if name not in self.state.setdefault("served_envs", []):
                self.state["served_envs"].append(name)
                save_state(self.state)
            return {"served": name}
        
        @self.app.post("/stop")
        def stop():
            self.shutdown_event.set()
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
        while not self.shutdown_event.is_set():
            time.sleep(0.2)

        self._cleanup_and_exit()

    def _signal_shutdown(self, *_):
        self.shutdown_event.set()

    def _cleanup_and_exit(self):
        print("\n[yellow]Shutting down VLA daemon[/yellow]")
        if PID_FILE.exists():
            PID_FILE.unlink()
        sys.exit(0)


