import os
import sys
import uuid
import time
import numpy as np
import mediapy
import signal
import uvicorn
import threading
from tqdm import tqdm
from typing import Optional, List
from rich import print
from pathlib import Path
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException
from vla.state.store import load_state, save_state
from vla.adapters import get_adapter
from vla.utils.paths import policy_dir
from vla.utils.logging import get_logger
from vla.utils.spec import parse_versioned
from vla.utils.lock import DaemonLock, is_daemon_running
from vla.utils.cleanup import CleanupManager, register_cleanup_handler
from vla.backend.registry import POLICY_BACKENDS, ENV_BACKENDS

log = get_logger("daemon")

class RunRequest(BaseModel):
    policy_id: str
    env_id: str
    task: str
    instruction: Optional[str] = None
    max_steps: int = 300
    seed: Optional[int] = None
    unnorm_key: Optional[str] = None
    save_video: bool = False
    video_path: Optional[str] = None

class PullPolicyRequest(BaseModel):
    spec: str  # e.g., "openvla:7b"

class ServePolicyRequest(BaseModel):
    spec: str  # e.g., "openvla:7b"
    device: str = "cuda:0"
    host_port: Optional[int] = None
    attn_implementation: str = "sdpa"

class ActRequest(BaseModel):
    policy_id: str
    image: str  # base64 encoded
    instruction: str
    unnorm_key: Optional[str] = None

class ActBatchRequest(BaseModel):
    policy_id: str
    image: List[str]  # base64 encoded
    instruction: List[str]
    unnorm_key: Optional[str] = None

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
        
        # Track env backends and handles
        self._env_backends = {}  # name -> backend instance
        self._env_handles = {}   # env_id -> (backend_name, EnvHandle)

        self._policy_backends = {}  # name -> backend instance
        self._policy_handles = {}   # policy_id -> (backend_name, PolicyHandle)

        self.shutdown_event = threading.Event()

        register_cleanup_handler("daemon", self._cleanup_all_containers)
        
        log.info(f"VLA Daemon initializing on port {port}")

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
            
            if req.policy_id not in self._policy_handles:
                raise HTTPException(
                    status_code=400,
                    detail=f"Policy '{req.policy_id}' not found. Available: {list(self._policy_handles.keys())}"
                )

            if req.env_id not in self._env_handles:
                raise HTTPException(
                    status_code=400,
                    detail=f"Env '{req.env_id}' not found. Available: {list(self._env_handles.keys())}"
                )
            
            policy_backend_name, policy_handle = self._policy_handles[req.policy_id]
            policy_backend = self._policy_backends[policy_backend_name]

            env_backend_name, env_handle = self._env_handles[req.env_id]
            env_backend = self._env_backends[env_backend_name]

            try:
                adapter = get_adapter(policy=policy_backend_name, env=env_backend_name)
            except Exception as e:
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to load adapter: {e}"
                )

            run_id = f"run-{uuid.uuid4().hex[:8]}"

            try:
                setup_result = env_backend.setup(
                    handle= env_handle,
                    task= req.task,
                    seed= req.seed
                )

                instruction = req.instruction or setup_result.get("instruction", "")
                if not instruction:
                    raise HTTPException(status_code=400, detail="No instruction provided and task has no default instruction")
                
                observation = env_backend.reset(handle=env_handle, seed=req.seed).get("observation", {})
                total_reward = 0
                frames = []

                for step in tqdm(range(req.max_steps)):                    
                    try:
                        payload = adapter.transform_obs(observation)

                    except Exception as e:
                        raise HTTPException(
                            status_code=500,
                            detail=f"Failed to transform observation: {e}. Keys: {list(observation.keys())}"
                        )
                    if req.save_video:
                        frames.append(self.get_image(payload))

                    raw_action = policy_backend.act(
                        handle=policy_handle,
                        payload=payload,  # base64 encoded, resized by adapter
                        instruction=instruction,
                        unnorm_key=req.unnorm_key,
                    )
                    
                    # Transform action using adapter
                    env_action = adapter.transform_action(raw_action)
                    
                    # Step environment with transformed action
                    step_result = env_backend.step(handle=env_handle, action=env_action)
                    
                    observation = step_result.get("observation", {})
                    reward = step_result.get("reward", 0.0)
                    terminated = step_result.get("terminated", False)
                    truncated = step_result.get("truncated", False)
                    
                    total_reward += reward
                    
                    # Check if done
                    if terminated or truncated:
                        break
                
                video_saved_path = None
                if req.save_video and frames:
                    try:                        
                        # Determine output path
                        if req.video_path:
                            output_path = Path(req.video_path)
                        else:
                            output_path = Path.home() / ".vla" / "videos" / f"{run_id}.mp4"
                        
                        output_path.parent.mkdir(parents=True, exist_ok=True)
                        
                        mediapy.write_video(output_path, frames, fps=15)
                        video_saved_path = str(output_path)

                    except Exception as video_err:
                        print(f"Warning: Failed to save video: {video_err}")
                
                return {
                    "run_id": run_id,
                    "success": terminated,
                    "policy_id": req.policy_id,
                    "env_id": req.env_id,
                    "task": req.task,
                    "instruction": instruction,
                    "steps": step,
                    "total_reward": total_reward,
                    "terminated": terminated,
                    "truncated": truncated,
                    "video_path": video_saved_path,
                    "adapter": adapter.get_info(),
                }
            
            except HTTPException:
                raise
            except Exception as e:
                import traceback
                traceback.print_exc()
                raise HTTPException(
                    status_code=500,
                    detail=f"Run failed: {str(e)}"
                )

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
            self._policy_backends[name] = backend

            model_path = policy_dir(name, version)

            # torch init stub happens here
            try:
                handle = backend.serve(
                    version=version,
                    model_path=model_path,
                    device=req.device,
                    host_port=req.host_port,
                    attn_implementation=req.attn_implementation
                )
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Failed to load '{policy_id}': {e}")

            self._policy_handles[handle.policy_id] = (name, handle)
            served = self.state.setdefault("served_policies", {})
            served[handle.policy_id] = handle.to_dict()

            return {
                "served": policy_id,
                "policy_id": handle.policy_id,
                "port": handle.port,
                "device": handle.device,
                "attn_implementation": handle.metadata.get("attn_implementation"),
            }
        
        @self.app.post("/policy/act")
        def policy_act(req: ActRequest):

            if req.policy_id not in self._policy_handles:
                raise HTTPException(status_code=400, detail=f"Policy '{req.policy_id}' not found. Available: {list(self._policy_handles.keys())}")

            backend_name, handle = self._policy_handles[req.policy_id]
            backend = self._policy_backends[backend_name]

            try:
                action = backend.act(
                    handle=handle,
                    image=req.image,  # Already base64
                    instruction=req.instruction,
                    unnorm_key=req.unnorm_key,
                )

                return {"action": action}
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/policy/info/{policy_id}")
        def get_policy_info(policy_id: str):
            if policy_id not in self._policy_handles:
                raise HTTPException(
                    status_code=400,
                    detail=f"Policy '{policy_id}' not found"
                )
            
            backend_name, handle = self._policy_handles[policy_id]
            backend = self._policy_backends[backend_name]
            
            try:
                return backend.get_info(handle)
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
            
        @self.app.post("/policy/stop/{policy_id}")
        def stop_policy(policy_id: str):
            if policy_id not in self._policy_handles:
                raise HTTPException(
                    status_code=400,
                    detail=f"Policy '{policy_id}' not found"
                )
            
            backend_name, handle = self._policy_handles[policy_id]
            backend = self._policy_backends.get(backend_name)
            
            if backend:
                try:
                    backend.stop(handle)
                except Exception as e:
                    raise HTTPException(status_code=500, detail=str(e))
            
            del self._policy_handles[policy_id]
            
            # Update state
            if policy_id in self.state.get("served_policies", {}):
                del self.state["served_policies"][policy_id]
            
            save_state(self.state)
            
            return {"stopped": policy_id}

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
        
        @self.app.post("/env/stop")
        def stop_env():
            
            for env_id in list(self._env_handles.keys()):
            
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
            
            return {"stopped": True}
        
        @self.app.post("/stop")
        def stop():
            self.shutdown_event.set()
            return {"stopped": True}
    
    def start(self):
        
        if is_daemon_running():
            print("[red]Deamon already running[/red]")
            sys.exit(1)

        self._lock = DaemonLock()
        if not self._lock.acquire():
            print("[red]Could not acquire daemon lock[/red]")
            sys.exit(1)

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

    def get_image(self, payload):

        images = []
        for key, val in payload.items():
            if "image" in key:
                images.append(np.array(val))
        
        images = np.concatenate(images, axis=1)
        return images

    def _loop(self):
        while not self.shutdown_event.is_set():
            time.sleep(0.2)

        self._cleanup_and_exit()

    def _signal_shutdown(self, *_):
        self.shutdown_event.set()

    def _cleanup_all_containers(self):
        """Cleanup all containers (called by CleanupManager)."""
        log.info("Cleaning up all containers...")
        
        # Stop all policy containers
        for policy_id, (backend_name, handle) in list(self._policy_handles.items()):
            backend = self._policy_backends.get(backend_name)
            if backend:
                try:
                    backend.stop(handle)
                    log.info(f"Stopped policy: {policy_id}")
                except Exception as e:
                    log.warning(f"Failed to stop policy {policy_id}: {e}")

        # Stop all env containers
        for env_id, (backend_name, handle) in list(self._env_handles.items()):
            backend = self._env_backends.get(backend_name)
            if backend:
                try:
                    backend.stop([handle])
                    log.info(f"Stopped env: {env_id}")
                except Exception as e:
                    log.warning(f"Failed to stop env {env_id}: {e}")
        
        self._policy_handles.clear()
        self._env_handles.clear()

    def _cleanup_and_exit(self):
        log.info("Shutting down VLA daemon")
        print("\n[yellow]Shutting down VLA daemon[/yellow]")

        self._cleanup_all_containers()

        # Release daemon lock
        if hasattr(self, '_lock'):
            self._lock.release()
        
        sys.exit(0)