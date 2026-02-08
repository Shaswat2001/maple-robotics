"""
MAPLE Daemon - Core orchestration server.

This module implements the main MAPLE daemon which provides a FastAPI-based
HTTP server for managing policy and environment containers, running evaluations,
and coordinating the entire MAPLE workflow.

The daemon handles:
- Policy and environment lifecycle (pull, serve, stop)
- Episode execution with policy-environment interaction
- Health monitoring of running containers
- State persistence via SQLite
- Graceful shutdown and cleanup
- Adapter-based transformation between policies and environments

Key components:
- FastAPI application with REST endpoints
- Container registry and health monitoring
- Policy and environment backend management
- Run orchestration with video recording
- Signal handling for graceful shutdown
"""

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
from rich import print
from pathlib import Path
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException
from typing import Optional, List, Dict, Any

from maple.state import store
from maple.adapters import get_adapter
from maple.utils.paths import policy_dir
from maple.utils.logging import get_logger
from maple.utils.spec import parse_versioned
from maple.backend.envs.base import EnvHandle
from maple.backend.policy.base import PolicyHandle
from maple.utils.health import HealthMonitor, HealthStatus
from maple.utils.lock import DaemonLock, is_daemon_running
from maple.backend.registry import POLICY_BACKENDS, ENV_BACKENDS
from maple.utils.cleanup import CleanupManager, register_cleanup_handler

log = get_logger("daemon")

class RunRequest(BaseModel):
    """Request model for running a policy on an environment task."""

    policy_id: str
    env_id: str
    task: str
    instruction: Optional[str] = None
    max_steps: int = 300
    seed: Optional[int] = None
    model_kwargs: Optional[Dict[str, Any]] = {}
    env_kwargs: Optional[Dict[str, Any]] = {}
    save_video: bool = False
    video_dir: Optional[str] = None

class PullPolicyRequest(BaseModel):
    """Request model for pulling a policy."""
    spec: str  # e.g., "openvla:7b"

class ServePolicyRequest(BaseModel):
    """Request model for serving a policy container."""
    spec: str  # e.g., "openvla:7b"
    device: str = "cpu"
    host_port: Optional[int] = None
    model_load_kwargs: Optional[Dict[str, Any]] = {}

class ActRequest(BaseModel):
    """Request model for single policy inference."""
    policy_id: str
    image: str  # base64 encoded
    instruction: str
    model_kwargs: Optional[Dict[str, Any]] = {}

class ActBatchRequest(BaseModel):
    """Request model for batched policy inference."""
    policy_id: str
    image: List[str]  # base64 encoded
    instruction: List[str]
    model_kwargs: Optional[Dict[str, Any]] = {}

class ServeEnvRequest(BaseModel):
    """Request model for serving environment containers."""
    name: str
    device: str = "cpu"
    num_envs: int = 1
    host_port: Optional[int] = None

class SetupEnvRequest(BaseModel):
    """Request model for setting up an environment with a task."""
    env_id: str
    task: str
    seed: Optional[int] = None
    env_kwargs: Optional[Dict[str, Any]] = {}

class ResetEnvRequest(BaseModel):
    """Request model for resetting an environment."""
    env_id: str
    seed: Optional[int] = None

class StepEnvRequest(BaseModel):
    """Request model for stepping an environment."""
    env_id: str
    action: List[float]

class EnvInfoRequest(BaseModel):
    """Request model for getting environment information."""
    env_id: str

class VLADaemon:
    """
    MAPLE daemon server for managing policies, environments, and evaluations.
    
    The daemon provides a FastAPI-based REST API for:
    - Pulling and serving policy models
    - Pulling and serving environment containers
    - Running evaluations with policy-environment interaction
    - Health monitoring of running containers
    - Graceful shutdown and cleanup
    
    The daemon uses backend plugins for policy and environment management,
    allowing extensibility to different model types and simulation platforms.
    """

    def __init__(self, port: int, device: str, health_check_interval: float = 30.0):
        """
        Initialize the MAPLE daemon.
        
        Sets up the FastAPI application, initializes backend registries,
        configures health monitoring, and registers cleanup handlers.
        
        :param port: Port number for the HTTP server to listen on.
        :param device: Default device for policy containers (e.g., 'cuda:0', 'cpu').
        :param health_check_interval: Interval in seconds between health checks.
        """

        self.running = True
        self.port = port
        self.device = device 
        health_interval = health_check_interval

        # Clear stale container records from previous daemon sessions
        store.clear_containers()
        
        # Track environment backends and handles
        # backend instance provides the interface implementation
        # handle represents a running container instance
        self._env_backends = {}  # name -> backend instance
        self._env_handles = {}   # env_id -> (backend_name, EnvHandle)

        # Track policy backends and handles
        self._policy_backends = {}  # name -> backend instance
        self._policy_handles = {}   # policy_id -> (backend_name, PolicyHandle)

        # Event for coordinating graceful shutdown
        self.shutdown_event = threading.Event()

        # Health monitoring for container liveness
        self._health_monitor = HealthMonitor(
            check_interval=health_interval,
            on_unhealthy=self._on_container_unhealthy,
        )

        # Register cleanup handler for graceful shutdown
        register_cleanup_handler("daemon", self._cleanup_all_containers)
        
        log.info(f"MAPLE Daemon initializing on port {port}")

        # Initialize FastAPI application
        self.app = FastAPI(title="MAPLE Daemon")

        @self.app.get("/status")
        def status() -> Dict[str, Any]:
            """
            Get daemon status and container information.
            
            Returns comprehensive status including running containers,
            pulled resources, and health monitor state.
            
            :return: Dictionary with daemon status and container information.
            """
            return {
                "running": True,
                "port": self.port,
                "device": self.device,
                "pulled": {
                    "policies": store.list_policies(),
                    "envs": store.list_envs(),
                },
                "serving": {
                    "policies": list(self._policy_handles.keys()),
                    "envs": list(self._env_handles.keys()),
                },
                "health_monitor": {
                    "running": self._health_monitor.is_running,
                    "containers": self._health_monitor.get_all_status(),
                },
            }
        
        @self.app.post("/run")
        def run(req: RunRequest) -> Dict[str, Any]:
            """
            Run a policy on an environment task.
            
            Orchestrates a complete evaluation episode:
            1. Validates policy and environment exist
            2. Loads appropriate adapter for transformation
            3. Sets up environment with task
            4. Runs episode loop with policy inference
            5. Optionally records video
            6. Returns episode results and metrics
            
            :param req: Run request with policy, env, task, and configuration.
            :return: Dictionary with episode results including success, steps, reward, and video path.
            """

            # Validate policy exists and is serving
            if req.policy_id not in self._policy_handles:
                raise HTTPException(
                    status_code=400,
                    detail=f"Policy '{req.policy_id}' not found. Available: {list(self._policy_handles.keys())}"
                )

            # Validate environment exists and is serving
            if req.env_id not in self._env_handles:
                raise HTTPException(
                    status_code=400,
                    detail=f"Env '{req.env_id}' not found. Available: {list(self._env_handles.keys())}"
                )
            
            # Get policy backend and handle
            policy_backend_name, policy_handle = self._policy_handles[req.policy_id]
            policy_backend = self._policy_backends[policy_backend_name]

            # Get environment backend and handle
            env_backend_name, env_handle = self._env_handles[req.env_id]
            env_backend = self._env_backends[env_backend_name]

            # Load adapter for policy-environment transformation
            try:
                adapter = get_adapter(policy=policy_backend_name, env=env_backend_name)
            except Exception as e:
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to load adapter: {e}"
                )

            # Generate unique run identifier
            run_id = f"run-{uuid.uuid4().hex[:8]}"

            try:
                # Setup environment with task
                setup_result = env_backend.setup(
                    handle=env_handle,
                    task=req.task,
                    seed=req.seed,
                    env_kwargs=req.env_kwargs
                )

                # Get instruction from request or task default
                instruction = req.instruction or setup_result.get("instruction", "")
                if not instruction:
                    raise HTTPException(status_code=400, detail="No instruction provided and task has no default instruction")
                
                # Reset environment and get initial observation
                observation = env_backend.reset(handle=env_handle, seed=req.seed).get("observation", {})
                total_reward = 0
                frames = []  # For video recording

                # Episode loop - run until max_steps or episode ends
                for step in tqdm(range(req.max_steps)):                    
                    # Transform observation to policy input format
                    try:
                        payload = adapter.transform_obs(observation)
                    except Exception as e:
                        raise HTTPException(
                            status_code=500,
                            detail=f"Failed to transform observation: {e}. Keys: {list(observation.keys())}"
                        )
                    
                    # Capture frame for video if requested
                    if req.save_video:
                        frames.append(self.get_image(payload))

                    # Get action from policy
                    raw_action = policy_backend.act(
                        handle=policy_handle,
                        payload=payload,  # base64 encoded, resized by adapter
                        instruction=instruction,
                        model_kwargs=req.model_kwargs,
                    )
                    
                    # Transform action to environment format
                    env_action = adapter.transform_action(raw_action)
                    
                    # Step environment with transformed action
                    step_result = env_backend.step(handle=env_handle, action=env_action)
                    
                    # Extract step results
                    observation = step_result.get("observation", {})
                    reward = step_result.get("reward", 0.0)
                    terminated = step_result.get("terminated", False)
                    truncated = step_result.get("truncated", False)
                    
                    total_reward += reward
                    
                    # Check if episode is done
                    if terminated or truncated:
                        break
                
                # Save video if requested and frames were captured
                video_saved_path = None
                if req.save_video and frames:
                    try:                        
                        # Determine output path
                        if req.video_dir:
                            output_dir = req.video_dir
                            output_path = Path(req.video_dir) / f"{run_id}.mp4"
                        else:
                            home_dir = os.path.expanduser("~")
                            output_dir = os.path.join(home_dir, ".maple", "videos")
                            output_path = os.path.join(output_dir, f"{run_id}.mp4")

                        # Create directory if it doesn't exist
                        os.makedirs(output_dir, exist_ok=True)

                        # Write video at 15 fps
                        mediapy.write_video(output_path, frames, fps=15)
                        video_saved_path = output_path

                    except Exception as video_err:
                        log.warning(f"Failed to save video: {video_err}")
                
                # Return episode results
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
                # Re-raise HTTP exceptions without wrapping
                raise
            except Exception as e:
                # Log full traceback and return error
                import traceback
                traceback.print_exc()
                raise HTTPException(
                    status_code=500,
                    detail=f"Run failed: {str(e)}"
                )

        @self.app.get("/policy/list")
        def policies() -> Dict[str, Any]:
            """
            List all pulled policies.
            
            :return: Dictionary containing list of pulled policy records.
            """
            return {"policies": store.list_policies()}

        @self.app.get("/env/list")
        def envs() -> Dict[str, Any]:
            """
            List all pulled environments.
            
            :return: Dictionary containing list of pulled environment records.
            """
            return {"envs": store.list_envs()}
        
        @self.app.post("/policy/pull")
        def pull_policy(req: PullPolicyRequest) -> Dict[str, Any]: 
            """
            Pull (download) a policy model.
            
            Downloads the policy model from a remote repository and registers
            it in the local store for later serving.
            
            :param req: Pull request with policy specification.
            :return: Dictionary with pull confirmation and manifest information.
            """
            # Parse version from spec
            name, version = parse_versioned(req.spec)

            # Validate backend exists
            if name not in POLICY_BACKENDS:
                raise HTTPException(status_code=400, detail=f"Unknown policy backend '{name}'")

            # Instantiate backend
            backend = POLICY_BACKENDS[name]()

            # Determine destination path
            dst = policy_dir(name, version)
            
            # Pull model to destination
            try:
                manifest = backend.pull(version=version, dst=dst)
            except Exception as e:
                raise HTTPException(status_code=400, detail=str(e))

            # Register in store
            store.add_policy(
                name=name,
                version=version,
                path=str(dst),
                repo=manifest.get("repo"),
                image=manifest.get("image")
            )

            return {"pulled": f"{name}:{version}", "manifest": manifest}

        @self.app.post("/env/pull")
        def pull_env(name: str) -> Dict[str, Any]:
            """
            Pull (download) an environment image.
            
            Downloads the environment container image and registers it in
            the local store for later serving.
            
            :param name: Environment backend name.
            :return: Dictionary with pull confirmation and metadata.
            """
            # Validate backend exists
            if name not in ENV_BACKENDS:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unknown env backend '{name}'. Available: {list(ENV_BACKENDS.keys())}"
                )
            
            # Instantiate backend
            backend = ENV_BACKENDS[name]()

            # Pull environment image
            try:
                meta = backend.pull()
            except Exception as e:
                raise HTTPException(
                    status_code=500,
                    detail=str(e)
                )

            # Register in store
            store.add_env(name=name, image=meta.get("image", ""))

            return {"env": name, "meta": meta}
        
        @self.app.post("/policy/serve")
        def serve_policy(req: ServePolicyRequest) -> Dict[str, Any]:
            """
            Serve a policy model in a container.
            
            Loads a previously pulled policy model and starts a container
            for serving inference requests. Registers with health monitor.
            
            :param req: Serve request with policy spec and configuration.
            :return: Dictionary with serving confirmation and container details.
            """
            # Parse version from spec
            name, version = parse_versioned(req.spec)
            policy_id = f"{name}:{version}"

            # Validate backend exists
            if name not in POLICY_BACKENDS:
                raise HTTPException(status_code=400, detail=f"Unknown policy backend '{name}'")

            # Validate policy was pulled
            if not store.get_policy(name, version):
                raise HTTPException(status_code=400, detail=f"Policy '{policy_id}' not pulled. Run 'maple pull policy {req.spec}' first.")

            # Instantiate backend
            backend = POLICY_BACKENDS[name]()
            self._policy_backends[name] = backend

            # Get model path
            model_path = policy_dir(name, version)

            # Serve policy (loads model and starts container)
            try:
                handle = backend.serve(
                    version=version,
                    model_path=model_path,
                    device=req.device,
                    host_port=req.host_port,
                    model_load_kwargs=req.model_load_kwargs
                )
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Failed to load '{policy_id}': {e}")

            # Register handle for future requests
            self._policy_handles[handle.policy_id] = (name, handle)
            
            # Store container information
            store.add_container(
                container_id=handle.container_id,
                type="policy",
                name=handle.policy_id,
                backend=name,
                host=handle.host,
                port=handle.port,
                status="ready",
                metadata=handle.metadata,
            )

            # Register with health monitor
            self._health_monitor.register(
                container_id=handle.container_id,
                name=handle.policy_id,
                check_fn=lambda h=handle, b=backend: self._check_policy_health(h, b),
                restart_fn=None,  # Could add auto-restart later
                auto_restart=False,
            )

            return {
                "served": policy_id,
                "policy_id": handle.policy_id,
                "port": handle.port,
                "device": handle.device,
                "model_load_kwargs": handle.metadata.get("model_load_kwargs"),
            }
        
        @self.app.post("/policy/act")
        def policy_act(req: ActRequest) -> Dict[str, Any]:
            """
            Get action from policy for a single observation.
            
            Sends an observation to a policy and returns the predicted action.
            Used for manual policy testing or custom evaluation loops.
            
            :param req: Act request with policy ID, image, and instruction.
            :return: Dictionary containing the predicted action.
            """
            # Validate policy exists
            if req.policy_id not in self._policy_handles:
                raise HTTPException(status_code=400, detail=f"Policy '{req.policy_id}' not found. Available: {list(self._policy_handles.keys())}")

            # Get policy backend and handle
            backend_name, handle = self._policy_handles[req.policy_id]
            backend = self._policy_backends[backend_name]

            # Run inference
            try:
                action = backend.act(
                    handle=handle,
                    image=req.image,  # Already base64
                    instruction=req.instruction,
                    model_kwargs=req.model_kwargs,
                )

                return {"action": action}
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/policy/info/{policy_id}")
        def get_policy_info(policy_id: str) -> Dict[str, Any]:
            """
            Get information about a policy container.
            
            Returns metadata about the policy including input/output specs
            and version information.
            
            :param policy_id: Identifier of the policy container.
            :return: Dictionary with policy metadata.
            """
            # Validate policy exists
            if policy_id not in self._policy_handles:
                raise HTTPException(
                    status_code=400,
                    detail=f"Policy '{policy_id}' not found"
                )
            
            # Get policy backend and handle
            backend_name, handle = self._policy_handles[policy_id]
            backend = self._policy_backends[backend_name]
            
            # Get info from backend
            try:
                return backend.get_info(handle)
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
            
        @self.app.post("/policy/stop/{policy_id}")
        def stop_policy(policy_id: str) -> Dict[str, Any]:
            """
            Stop a policy container.
            
            Stops the policy container, unregisters from health monitor,
            and removes from tracking.
            
            :param policy_id: Identifier of the policy to stop.
            :return: Dictionary confirming the stop.
            """
            # Validate policy exists
            if policy_id not in self._policy_handles:
                raise HTTPException(
                    status_code=400,
                    detail=f"Policy '{policy_id}' not found"
                )
            
            # Get policy backend and handle
            backend_name, handle = self._policy_handles[policy_id]
            backend = self._policy_backends.get(backend_name)
            
            # Stop container
            if backend:
                try:
                    backend.stop(handle)
                except Exception as e:
                    raise HTTPException(status_code=500, detail=str(e))
            
            # Unregister from health monitor and remove from store
            if handle.container_id:
                self._health_monitor.unregister(handle.container_id)
                store.remove_container(handle.container_id)

            # Remove from tracking
            del self._policy_handles[policy_id]
            
            return {"stopped": policy_id}

        @self.app.post("/env/serve")
        def serve_env(req: ServeEnvRequest) -> Dict[str, Any]:
            """
            Serve one or more environment containers.
            
            Starts environment container(s) for running evaluations.
            Multiple instances can be created for parallel execution.
            
            :param req: Serve request with environment name and count.
            :return: Dictionary with serving confirmation and container details.
            """
            name = req.name
            host_port = req.host_port
            device=req.device
            num_envs = req.num_envs

            # Validate environment was pulled
            if not store.get_env(name):
                raise HTTPException(
                    status_code=400, 
                    detail=f"Env '{name}' not pulled. Run 'maple pull env {name}' first."
                )
            
            # Validate backend exists
            if name not in ENV_BACKENDS:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unknown env backend '{name}'"
                )

            # Instantiate backend
            backend = ENV_BACKENDS[name]()
            self._env_backends[name] = backend
            
            # Serve environments (can create multiple instances)
            try:
                handles = backend.serve(num_envs= num_envs,
                                        device= device,
                                        host_port= host_port)
            except Exception as e:
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to serve env '{name}': {e}"
                )
            
            # Register each handle
            for handle in handles:
                self._env_handles[handle.env_id] = (name, handle)
                
                # Store container information
                store.add_container(
                    container_id=handle.container_id,
                    type="env",
                    name=handle.env_id,
                    backend=name,
                    host=handle.host,
                    port=handle.port,
                    status="ready",
                    metadata=handle.metadata,
                )

                # Register with health monitor
                self._health_monitor.register(
                    container_id=handle.container_id,
                    name=handle.env_id,
                    check_fn=lambda h=handle, b=backend: self._check_env_health(h, b),
                    auto_restart=False,
                )
            
            return {
                "served": name,
                "device": handle.device,
                "num_envs": len(handles),
                "env_ids": [h.env_id for h in handles],
                "ports": [h.port for h in handles],
            }
        
        @self.app.post("/env/setup")
        def setup_env(req: SetupEnvRequest) -> Dict[str, Any]:
            """
            Setup an environment with a specific task.
            
            Initializes the environment with task-specific configuration
            and returns task metadata including instruction.
            
            :param req: Setup request with env ID and task spec.
            :return: Dictionary with task information.
            """
            # Validate environment exists
            if req.env_id not in self._env_handles:
                raise HTTPException(
                    status_code=400,
                    detail=f"Env '{req.env_id}' not found. Available: {list(self._env_handles.keys())}"
                )
            
            # Get environment backend and handle
            backend_name, handle = self._env_handles[req.env_id]
            backend = self._env_backends[backend_name]
            
            # Setup task
            try:
                result = backend.setup(handle, task=req.task, seed=req.seed, env_kwargs= req.env_kwargs)
                return result
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/env/reset")
        def reset_env(req: ResetEnvRequest) -> Dict[str, Any]:
            """
            Reset an environment to initial state.
            
            Resets the environment and returns the initial observation.
            
            :param req: Reset request with env ID and optional seed.
            :return: Dictionary with initial observation.
            """
            # Validate environment exists
            if req.env_id not in self._env_handles:
                raise HTTPException(
                    status_code=400,
                    detail=f"Env '{req.env_id}' not found"
                )
            
            # Get environment backend and handle
            backend_name, handle = self._env_handles[req.env_id]
            backend = self._env_backends[backend_name]
            
            # Reset environment
            try:
                result = backend.reset(handle, seed=req.seed)
                return result
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/env/step")
        def step_env(req: StepEnvRequest) -> Dict[str, Any]:
            """
            Step the environment with an action.
            
            Executes one step in the environment and returns the resulting
            observation, reward, and termination flags.
            
            :param req: Step request with env ID and action.
            :return: Dictionary with step results (observation, reward, terminated, truncated).
            """
            # Validate environment exists
            if req.env_id not in self._env_handles:
                raise HTTPException(
                    status_code=400,
                    detail=f"Env '{req.env_id}' not found"
                )
            
            # Get environment backend and handle
            backend_name, handle = self._env_handles[req.env_id]
            backend = self._env_backends[backend_name]
            
            # Step environment
            try:
                result = backend.step(handle, action=req.action)
                return result
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/env/info/{env_id}")
        def get_env_info(env_id: str) -> Dict[str, Any]:
            """
            Get information about an environment container.
            
            Returns metadata about the environment including current task,
            suite, and action space information.
            
            :param env_id: Identifier of the environment container.
            :return: Dictionary with environment metadata.
            """
            # Validate environment exists
            if env_id not in self._env_handles:
                raise HTTPException(
                    status_code=400,
                    detail=f"Env '{env_id}' not found"
                )
            
            # Get environment backend and handle
            backend_name, handle = self._env_handles[env_id]
            backend = self._env_backends[backend_name]
            
            # Get info from backend
            try:
                result = backend.get_info(handle)
                return result
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/env/tasks/{backend_name}")
        def list_env_tasks(backend_name: str, suite: Optional[str] = None) -> Dict[str, Any]:
            """
            List available tasks for an environment backend.
            
            Returns all tasks available in the specified environment backend,
            optionally filtered by suite name.
            
            :param backend_name: Name of the environment backend.
            :param suite: Optional suite name to filter results.
            :return: Dictionary mapping suite names to task lists.
            """
            # Validate backend exists
            if backend_name not in ENV_BACKENDS:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unknown env backend '{backend_name}'"
                )
            
            # Use existing backend if available, otherwise create new instance
            if backend_name in self._env_backends:
                backend = self._env_backends[backend_name]
            else:
                backend = ENV_BACKENDS[backend_name]()
            
            # List tasks
            try:
                return backend.list_tasks(suite=suite)
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/env/stop/{env_id}")
        def stop_single_env(env_id: str) -> Dict[str, Any]:
            """
            Stop a single environment container.
            
            Stops the specified environment container, unregisters from
            health monitor, and removes from tracking.
            
            :param env_id: Identifier of the environment to stop.
            :return: Dictionary confirming the stop.
            """
            # Validate environment exists
            if env_id not in self._env_handles:
                raise HTTPException(
                    status_code=400,
                    detail=f"Env '{env_id}' not found"
                )
            
            # Get environment backend and handle
            backend_name, handle = self._env_handles[env_id]
            backend = self._env_backends.get(backend_name)
            
            # Stop container
            if backend:
                try:
                    backend.stop([handle])
                except Exception as e:
                    raise HTTPException(status_code=500, detail=str(e))
                        
            # Unregister from health monitor and remove from store
            if handle.container_id:
                self._health_monitor.unregister(handle.container_id)
                store.remove_container(handle.container_id)
            
            # Remove from tracking
            del self._env_handles[env_id]
            
            return {"stopped": env_id}
        
        @self.app.post("/env/stop")
        def stop_env() -> Dict[str, Any]:
            """
            Stop all environment containers.
            
            Stops all running environment containers, unregisters from
            health monitor, and clears tracking.
            
            :return: Dictionary confirming all environments stopped.
            """
            # Iterate over copy of keys since we're modifying the dict
            for env_id in list(self._env_handles.keys()):
            
                # Get environment backend and handle
                backend_name, handle = self._env_handles[env_id]
                backend = self._env_backends.get(backend_name)
                
                # Stop container
                if backend:
                    try:
                        backend.stop([handle])
                    except Exception as e:
                        raise HTTPException(status_code=500, detail=str(e))
                
                # Unregister from health monitor and remove from store
                if handle.container_id:
                    self._health_monitor.unregister(handle.container_id)
                    store.remove_container(handle.container_id)
            
                # Remove from tracking
                del self._env_handles[env_id]
            
            return {"stopped": True}
        
        @self.app.post("/stop")
        def stop() -> Dict[str, Any]:
            """
            Stop the daemon.
            
            Triggers graceful shutdown of the daemon, which will clean up
            all containers and release the daemon lock.
            
            :return: Dictionary confirming shutdown initiated.
            """
            self.shutdown_event.set()
            return {"stopped": True}
    
    def start(self) -> None:
        """
        Start the daemon server.
        
        Acquires the daemon lock, starts the health monitor, launches the
        FastAPI server in a background thread, and enters the main event loop.
        Handles graceful shutdown on SIGINT/SIGTERM.
        """
        # Check if another daemon is already running
        if is_daemon_running():
            print("[red]Daemon already running[/red]")
            sys.exit(1)

        # Acquire daemon lock to prevent multiple instances
        self._lock = DaemonLock()
        if not self._lock.acquire():
            print("[red]Could not acquire daemon lock[/red]")
            sys.exit(1)

        print(
            f"[bold cyan]MAPLE daemon started[/bold cyan] "
            f"(port={self.port}, device={self.device})"
        )

        # Register signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_shutdown)
        signal.signal(signal.SIGTERM, self._signal_shutdown)
        
        # Start health monitoring
        self._health_monitor.start()

        # Start FastAPI server in background thread
        thread = threading.Thread(target=self._run_api, daemon=True)
        thread.start()

        # Enter main event loop
        self._loop()

    def _run_api(self) -> None:
        """
        Run the FastAPI server.
        
        Starts uvicorn server with the FastAPI application. Runs in a
        background thread started by start().
        """
        uvicorn.run(
            self.app,
            host="0.0.0.0",
            port=self.port,
            log_level="error",
        )

    def get_image(self, payload: Dict[str, Any]) -> np.ndarray:
        """
        Extract and concatenate images from payload for video recording.
        
        Searches for image keys in the payload dictionary and concatenates
        them horizontally for visualization.
        
        :param payload: Dictionary containing observation data with image keys.
        :return: Numpy array of concatenated images.
        """
        images = []
        for key, val in payload.items():
            if "image" in key:
                images.append(np.array(val))
        
        # Concatenate horizontally
        images = np.concatenate(images, axis=1)
        return images

    def _loop(self) -> None:
        """
        Main event loop.
        
        Waits for shutdown event, then initiates cleanup and exit.
        Runs in the main thread after start() is called.
        """
        while not self.shutdown_event.is_set():
            time.sleep(0.2)

        self._cleanup_and_exit()

    def _signal_shutdown(self, *_):
        """
        Signal handler for SIGINT and SIGTERM.
        
        Sets the shutdown event to trigger graceful shutdown.
        """
        self.shutdown_event.set()

    def _check_policy_health(self, handle: PolicyHandle, backend) -> bool:
        """
        Health check function for policy containers.
        
        Called by health monitor to verify policy container is responsive.
        
        :param handle: Policy handle to check.
        :param backend: Policy backend instance.
        :return: True if healthy, False if unhealthy.
        """
        try:
            result = backend.health(handle)
            return result.get("status") != "error"
        except Exception:
            return False
    
    def _check_env_health(self, handle: EnvHandle, backend) -> bool:
        """
        Health check function for environment containers.
        
        Called by health monitor to verify environment container is responsive.
        
        :param handle: Environment handle to check.
        :param backend: Environment backend instance.
        :return: True if healthy, False if unhealthy.
        """
        try:
            result = backend.health(handle)
            return result.get("status") != "error"
        except Exception:
            return False
    
    def _on_container_unhealthy(self, container) -> None:
        """
        Callback when a container becomes unhealthy.
        
        Called by health monitor when a container fails health checks.
        Updates container status in the store.
        
        :param container: Container that became unhealthy.
        """
        log.warning(f"Container unhealthy: {container.name}")
        store.update_container_status(container.container_id, "unhealthy")

    def _cleanup_all_containers(self) -> None:
        """
        Cleanup all containers.
        
        Stops all policy and environment containers, unregisters from health
        monitor, and clears tracking dictionaries. Called by CleanupManager
        during shutdown.
        """
        log.info("Cleaning up all containers...")
        
        # Stop health monitor
        self._health_monitor.stop()

        # Stop all policy containers
        for policy_id, (backend_name, handle) in list(self._policy_handles.items()):
            backend = self._policy_backends.get(backend_name)
            if backend:
                try:
                    backend.stop(handle)
                    log.info(f"Stopped policy: {policy_id}")
                except Exception as e:
                    log.warning(f"Failed to stop policy {policy_id}: {e}")

            # Cleanup tracking
            if handle.container_id:
                self._health_monitor.unregister(handle.container_id)
                store.remove_container(handle.container_id)

        # Stop all env containers
        for env_id, (backend_name, handle) in list(self._env_handles.items()):
            backend = self._env_backends.get(backend_name)
            if backend:
                try:
                    backend.stop([handle])
                    log.info(f"Stopped env: {env_id}")
                except Exception as e:
                    log.warning(f"Failed to stop env {env_id}: {e}")

            # Cleanup tracking
            if handle.container_id:
                self._health_monitor.unregister(handle.container_id)
                store.remove_container(handle.container_id)

        # Clear all tracking dictionaries
        self._policy_handles.clear()
        self._env_handles.clear()

    def _cleanup_and_exit(self) -> None:
        """
        Perform final cleanup and exit.
        
        Cleans up all containers, releases the daemon lock, and exits
        the process. Called when shutdown event is set.
        """
        log.info("Shutting down MAPLE daemon")

        # Cleanup all containers
        self._cleanup_all_containers()

        # Release daemon lock
        if hasattr(self, '_lock'):
            self._lock.release()
        
        sys.exit(0)