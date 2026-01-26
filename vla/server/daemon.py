import os
import sys
import time
import signal
import uvicorn
import threading
from typing import Optional, List
from rich import print
from pathlib import Path
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException
from vla.state.store import load_state, save_state
from vla.scheduler import Scheduler
from vla.utils.paths import policy_dir
from vla.utils.spec import parse_versioned
from vla.backend.policy.registry import POLICY_BACKENDS
from vla.backend.envs.registry import ENV_BACKENDS
from vla.backend.envs.base import EnvHandle

PID_FILE = Path.home() / ".vla" / "daemon.pid"


class RunRequest(BaseModel):
    policy: str
    env: str
    task: str
    instruction: Optional[str] = None


class PullPolicyRequest(BaseModel):
    spec: str  # e.g., "openvla:7b"


class ServePolicyRequest(BaseModel):
    spec: str  # e.g., "openvla:7b"


class ServeEnvRequest(BaseModel):
    name: str
    num_envs: int = 1


class SetupEnvRequest(BaseModel):
    env_id: str
    task: str
    seed: Optional[int] = None


class ResetEnvRequest(BaseModel):
    env_id: str
    seed: Optional[int] = None


class StepEnvRequest(BaseModel):
    env_id: str
    action: List[float]


class EnvInfoRequest(BaseModel):
    env_id: str

class VLADaemon:

    def __init__(self, port: int, device: str):
        self.running = True
        self.port = port
        self.device = device 
        self.state = load_state()

        self.scheduler = Scheduler()
        
        # Track env backends and handles
        self._env_backends = {}  # name -> backend instance
        self._env_handles = {}   # env_id -> (backend_name, EnvHandle)

        self.shutdown_event = threading.Event()

        self.app = FastAPI(title= "VLA Daemon")

        @self.app.get("/status")
        def status():

            status = self.state.copy()
            for name, data in status.items():

                if "backend" in data:
                    del data["backend"]
            return {
                "running": True,
                "port": self.port,
                "device": self.device,
                "state": status
            }
        
        @self.app.post("/run")
        def run(req: RunRequest):
            
            if req.policy not in self.state.get("served_policies", []):
                raise HTTPException(
                    status_code=400,
                    detail=f"Policy '{req.policy}' not served"
                )

            if req.env not in self.state.get("served_envs", {}):
                raise HTTPException(
                    status_code=400,
                    detail=f"Env '{req.env}' not served"
                )
            
            meta = self.scheduler.submit(req.model_dump())

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
        def pull_env(name: str):

            if name not in ENV_BACKENDS:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unknown env backend '{name}'. Available: {list(ENV_BACKENDS.keys())}"
                )
            
            backend = ENV_BACKENDS[name]()

            try:
                meta = backend.pull()
            except Exception as e:
                raise HTTPException(
                    status_code=500,
                    detail=str(e)
                )

            if name not in self.state["envs"]:
                self.state["envs"].append(name)
                save_state(self.state)
            return {"env": name, "meta": meta}
        
        @self.app.post("/policy/serve")
        def serve_policy(req: ServePolicyRequest):
            name, version = parse_versioned(req.spec)
            policy_id = f"{name}:{version}"

            if name not in POLICY_BACKENDS:
                raise HTTPException(status_code=400, detail=f"Unknown policy backend '{name}'")

            if policy_id not in self.state.get("policies", []):
                raise HTTPException(status_code=400, detail=f"Policy '{policy_id}' not pulled")

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

            return {"served": policy_id}
        
        @self.app.post("/env/serve")
        def serve_env(req: ServeEnvRequest):

            name = req.name
            num_envs = req.num_envs
            
            if name not in self.state["envs"]:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Env '{name}' not pulled. Run 'vla pull env {name}' first."
                )
            
            if name not in ENV_BACKENDS:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unknown env backend '{name}'"
                )

            backend = ENV_BACKENDS[name]()
            self._env_backends[name] = backend
            
            try:
                handles = backend.serve(num_envs)
            except Exception as e:
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to serve env '{name}': {e}"
                )
            
            # Track handles
            served_envs = self.state.setdefault("served_envs", {})
            if name not in served_envs:
                served_envs[name] = {"handles": []}
            
            for handle in handles:
                self._env_handles[handle.env_id] = (name, handle)
                served_envs[name]["handles"].append(handle.to_dict())
            
            return {
                "served": name,
                "num_envs": len(handles),
                "env_ids": [h.env_id for h in handles],
            }
        
        @self.app.post("/env/setup")
        def setup_env(req: SetupEnvRequest):
            if req.env_id not in self._env_handles:
                raise HTTPException(
                    status_code=400,
                    detail=f"Env '{req.env_id}' not found. Available: {list(self._env_handles.keys())}"
                )
            
            backend_name, handle = self._env_handles[req.env_id]
            backend = self._env_backends[backend_name]
            
            try:
                result = backend.setup(handle, task=req.task, seed=req.seed)
                return result
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/env/reset")
        def reset_env(req: ResetEnvRequest):
            if req.env_id not in self._env_handles:
                raise HTTPException(
                    status_code=400,
                    detail=f"Env '{req.env_id}' not found"
                )
            
            backend_name, handle = self._env_handles[req.env_id]
            backend = self._env_backends[backend_name]
            
            try:
                result = backend.reset(handle, seed=req.seed)
                return result
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/env/step")
        def step_env(req: StepEnvRequest):
            if req.env_id not in self._env_handles:
                raise HTTPException(
                    status_code=400,
                    detail=f"Env '{req.env_id}' not found"
                )
            
            backend_name, handle = self._env_handles[req.env_id]
            backend = self._env_backends[backend_name]
            
            try:
                result = backend.step(handle, action=req.action)
                return result
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/env/info/{env_id}")
        def get_env_info(env_id: str):
            if env_id not in self._env_handles:
                raise HTTPException(
                    status_code=400,
                    detail=f"Env '{env_id}' not found"
                )
            
            backend_name, handle = self._env_handles[env_id]
            backend = self._env_backends[backend_name]
            
            try:
                result = backend.get_info(handle)
                return result
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/env/tasks/{backend_name}")
        def list_env_tasks(backend_name: str, suite: Optional[str] = None):
            if backend_name not in ENV_BACKENDS:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unknown env backend '{backend_name}'"
                )
            
            # Use existing backend if available
            if backend_name in self._env_backends:
                backend = self._env_backends[backend_name]
            else:
                backend = ENV_BACKENDS[backend_name]()
            
            try:
                return backend.list_tasks(suite=suite)
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/env/stop/{env_id}")
        def stop_single_env(env_id: str):
            if env_id not in self._env_handles:
                raise HTTPException(
                    status_code=400,
                    detail=f"Env '{env_id}' not found"
                )
            
            backend_name, handle = self._env_handles[env_id]
            backend = self._env_backends.get(backend_name)
            
            if backend:
                try:
                    backend.stop([handle])
                except Exception as e:
                    raise HTTPException(status_code=500, detail=str(e))
            
            del self._env_handles[env_id]
            
            # Update state
            if backend_name in self.state.get("served_envs", {}):
                handles = self.state["served_envs"][backend_name].get("handles", [])
                self.state["served_envs"][backend_name]["handles"] = [
                    h for h in handles if h.get("env_id") != env_id
                ]
                save_state(self.state)
            
            return {"stopped": env_id}
        
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

        signal.signal(signal.SIGINT, self._signal_shutdown)
        signal.signal(signal.SIGTERM, self._signal_shutdown)

        thread = threading.Thread(target=self._run_api, daemon=True)
        thread.start()

        self._loop()

    def _run_api(self):
        uvicorn.run(
            self.app,
            host="0.0.0.0",
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

        # Stop all env containers
        for env_id, (backend_name, handle) in list(self._env_handles.items()):
            backend = self._env_backends.get(backend_name)
            if backend:
                try:
                    backend.stop([handle])
                    print(f"  Stopped env: {env_id}")
                except Exception as e:
                    print(f"  [red]Failed to stop {env_id}: {e}[/red]")

        if PID_FILE.exists():
            PID_FILE.unlink()
        
        sys.exit(0)