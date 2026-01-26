import uuid
import time
import requests
from typing import List, Optional, Dict, Any

import docker
from docker.errors import NotFound, APIError

from vla.backend.envs.base import EnvBackend, EnvHandle


class LiberoEnvBackend(EnvBackend):
    """Backend for LIBERO manipulation environments."""
    
    name = "libero"
    
    IMAGE = "shaswatai/robotics_envs:libero"
    CONTAINER_PORT = 8000
    STARTUP_TIMEOUT = 120  # seconds to wait for container to be ready
    HEALTH_CHECK_INTERVAL = 2  # seconds between health checks
    
    def __init__(self):
        self.client = docker.from_env()
        self._active_handles: Dict[str, EnvHandle] = {}

    def _get_base_url(self, handle: EnvHandle) -> str:
        """Get base URL for RPC calls."""
        return f"http://{handle.host}:{handle.port}"

    def _wait_for_ready(self, handle: EnvHandle) -> bool:
        """Wait for container to be ready to accept requests."""
        base_url = self._get_base_url(handle)
        deadline = time.time() + self.STARTUP_TIMEOUT
        
        while time.time() < deadline:
            try:
                resp = requests.get(f"{base_url}/health", timeout=5)
                if resp.status_code == 200:
                    return True
            except requests.exceptions.ConnectionError:
                pass
            except requests.exceptions.Timeout:
                pass
            
            time.sleep(self.HEALTH_CHECK_INTERVAL)
        
        return False

    def pull(self) -> dict:
        """Pull or build the LIBERO Docker image."""
        try:
            # First try to pull from registry
            image = self.client.images.pull(self.IMAGE)
            return {
                "env": self.name,
                "image": self.IMAGE,
                "source": "pulled",
            }
        except APIError:
            # If pull fails, try to build locally
            # This requires the Dockerfile to be present
            pass
        
        # Check if image exists locally
        try:
            image = self.client.images.get(self.IMAGE)
            return {
                "env": self.name,
                "image": self.IMAGE,
                "source": "local",
            }
        except NotFound:
            raise RuntimeError(
                f"Image {self.IMAGE} not found. "
                f"Build it with: docker build -t {self.IMAGE} docker/libero/"
            )
        
    def serve(self, num_envs: int = 1) -> List[EnvHandle]:
        """Start LIBERO environment containers."""
        handles = []
        
        for i in range(num_envs):
            env_id = f"libero-{uuid.uuid4().hex[:8]}"
            
            try:
                container = self.client.containers.run(
                    self.IMAGE,
                    detach=True,
                    remove=True,
                    name=env_id,
                    ports={f"{self.CONTAINER_PORT}/tcp": None},  # random host port
                    labels={
                        "vla.env": self.name,
                        "vla.env_id": env_id,
                    },
                    # Resource limits
                    mem_limit="4g",
                    # Environment variables
                    environment={
                        "MUJOCO_GL": "osmesa",
                    },
                )
                
                # Reload to get port mapping
                container.reload()
                port_info = container.attrs["NetworkSettings"]["Ports"]
                host_port = int(port_info[f"{self.CONTAINER_PORT}/tcp"][0]["HostPort"])
                
                handle = EnvHandle(
                    env_id=env_id,
                    backend_name=self.name,
                    host="127.0.0.1",
                    port=host_port,
                    container_id=container.id,
                    metadata={"status": "starting"},
                )
                
                # Wait for container to be ready
                if self._wait_for_ready(handle):
                    handle.metadata["status"] = "ready"
                else:
                    # Cleanup failed container
                    try:
                        container.stop(timeout=5)
                    except Exception:
                        pass
                    raise RuntimeError(f"Container {env_id} failed to start within {self.STARTUP_TIMEOUT}s")
                
                self._active_handles[env_id] = handle
                handles.append(handle)
                
            except Exception as e:
                # Cleanup any started containers on failure
                for h in handles:
                    try:
                        self._stop_single(h)
                    except Exception:
                        pass
                raise RuntimeError(f"Failed to start env {i+1}/{num_envs}: {e}")
        
        return handles

    def _stop_single(self, handle: EnvHandle) -> None:
        """Stop a single container."""
        if handle.container_id:
            try:
                container = self.client.containers.get(handle.container_id)
                container.stop(timeout=10)
            except NotFound:
                pass
        
        if handle.env_id in self._active_handles:
            del self._active_handles[handle.env_id]

    def stop(self, handles: List[EnvHandle]) -> None:
        """Stop environment containers."""
        for handle in handles:
            self._stop_single(handle)
    
    def setup(self, handle: EnvHandle, task: str, seed: Optional[int] = None) -> dict:
        """Setup environment with a specific task."""
        base_url = self._get_base_url(handle)
        
        payload = {"task": task}
        if seed is not None:
            payload["seed"] = seed
            
        try:
            resp = requests.post(f"{base_url}/setup", json=payload, timeout=60)
            resp.raise_for_status()
            result = resp.json()
            
            # Update handle metadata
            handle.metadata["task"] = result.get("task")
            handle.metadata["instruction"] = result.get("instruction")
            handle.metadata["status"] = "setup"
            
            return result
            
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Failed to setup env {handle.env_id}: {e}")
    
    def reset(self, handle: EnvHandle, seed: Optional[int] = None) -> dict:
        """Reset the environment."""
        base_url = self._get_base_url(handle)
        
        params = {}
        if seed is not None:
            params["seed"] = seed
            
        try:
            resp = requests.post(f"{base_url}/reset", params=params, timeout=30)
            resp.raise_for_status()
            return resp.json()
            
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Failed to reset env {handle.env_id}: {e}")
    
    def step(self, handle: EnvHandle, action: List[float]) -> dict:
        """Take a step in the environment."""
        base_url = self._get_base_url(handle)
        
        try:
            resp = requests.post(
                f"{base_url}/step",
                json={"action": action},
                timeout=30,
            )
            resp.raise_for_status()
            return resp.json()
            
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Failed to step env {handle.env_id}: {e}")
    
    def get_info(self, handle: EnvHandle) -> dict:
        """Get environment info."""
        base_url = self._get_base_url(handle)
        
        try:
            resp = requests.get(f"{base_url}/info", timeout=10)
            resp.raise_for_status()
            return resp.json()
            
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Failed to get info for env {handle.env_id}: {e}")
    
    def list_tasks(self, suite: Optional[str] = None) -> dict:
        """
        List available tasks.
        
        Note: This requires a running container. If no container is running,
        returns a static list of known task suites.
        """
        # If we have an active handle, use it to get dynamic task list
        if self._active_handles:
            handle = next(iter(self._active_handles.values()))
            base_url = self._get_base_url(handle)
            
            try:
                params = {}
                if suite:
                    params["suite"] = suite
                    
                resp = requests.get(f"{base_url}/tasks", params=params, timeout=30)
                resp.raise_for_status()
                return resp.json()
                
            except requests.exceptions.RequestException:
                pass
        
        # Fallback: return static task suite info
        return {
            "libero_spatial": {"description": "10 spatial reasoning tasks", "count": 10},
            "libero_object": {"description": "10 object manipulation tasks", "count": 10},
            "libero_goal": {"description": "10 goal-conditioned tasks", "count": 10},
            "libero_10": {"description": "10 diverse tasks", "count": 10},
            "libero_90": {"description": "90 diverse tasks", "count": 90},
            "_note": "Start an env to get full task listings with instructions",
        }
    
    def health(self, handle: EnvHandle) -> dict:
        """Check health of a specific env instance."""
        base_url = self._get_base_url(handle)
        
        try:
            resp = requests.get(f"{base_url}/health", timeout=5)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.RequestException as e:
            return {"status": "error", "error": str(e)}