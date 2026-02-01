import uuid
import time
import requests
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

import docker
from docker.errors import NotFound, APIError

from maple.utils.logging import get_logger
from maple.utils.retry import retry
from maple.utils.cleanup import register_container, unregister_container

log = get_logger("env.base")

@dataclass
class EnvHandle:
    env_id: str
    backend_name: str
    host: str
    port: str
    container_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "env_id": self.env_id,
            "backend_name": self.backend_name,
            "host": self.host,
            "port": self.port,
            "container_id": self.container_id,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, d: dict) -> "EnvHandle":
        return cls(**d)

class EnvBackend(ABC):
    name: str
    IMAGE: str
    CONTAINER_PORT: int = 8000
    STARTUP_TIMEOUT: int = 120
    HEALTH_CHECK_INTERVAL: int = 2
    MEMORY_LIMIT: str = "4g"

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

        log.debug(f"Waiting for container {handle.env_id} to be ready....")
        
        while time.time() < deadline:
            try:
                resp = requests.get(f"{base_url}/health", timeout=5)
                if resp.status_code == 200:
                    log.debug(f"Container {handle.env_id} is ready")
                    return True
            except requests.exceptions.ConnectionError:
                pass
            except requests.exceptions.Timeout:
                pass
            
            time.sleep(self.HEALTH_CHECK_INTERVAL)
        
        log.error(f"Container {handle.env_id} failed to become ready within {self.STARTUP_TIMEOUT}s")
        return False
    
    def health(self, handle: EnvHandle) -> dict:
        """Check health of a specific env instance."""
        base_url = self._get_base_url(handle)
        
        try:
            resp = requests.get(f"{base_url}/health", timeout=5)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.RequestException as e:
            log.warning(f"Health check failed for {handle.env_id}: {e}")
            return {"status": "error", "error": str(e)}

    def pull(self) -> dict:
        """Pull or build the LIBERO Docker image."""
        try:
            log.info(f"Pulling Docker image {self.IMAGE}...")
            image = self.client.images.pull(self.IMAGE)
            log.info(f"Image pulled: {self.IMAGE}")
            return {
                "env": self.name,
                "image": self.IMAGE,
                "source": "pulled",
            }
        except APIError:
            pass
        
        # Check if image exists locally
        try:
            image = self.client.images.get(self.IMAGE)
            log.debug(f"Image found locally: {self.IMAGE}")
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
    
    def serve(self, num_envs: int = 1, host_port: Optional[int] = None) -> List[EnvHandle]:
        """Start environment containers."""
        handles = []
        
        if host_port is not None and num_envs > 1:
            raise ValueError("host_port can only be specified when num_envs=1")
        
        log.info(f"Starting {num_envs} {self.name} environment(s)...")
        
        for i in range(num_envs):
            env_id = f"{self.name}-{uuid.uuid4().hex[:8]}"
            
            if host_port is not None:
                port_mapping = {f"{self.CONTAINER_PORT}/tcp": host_port}
            else:
                port_mapping = {f"{self.CONTAINER_PORT}/tcp": None}
            
            container = None
            try:
                # Get env-specific config
                config = self._get_container_config()
                
                container = self.client.containers.run(
                    self.IMAGE,
                    detach=True,
                    remove=True,
                    name=env_id,
                    ports=port_mapping,
                    labels={
                        "vla.env": self.name,
                        "vla.env_id": env_id,
                    },
                    mem_limit=self.MEMORY_LIMIT,
                    environment=config.get("environment", {}),
                    volumes=config.get("volumes", {}),
                    device_requests=config.get("device_requests", []),
                )
                
                register_container(container.id, env_id)
                log.debug(f"Container started: {env_id} ({container.id[:12]})")
                
                # Wait for port mapping
                actual_port = self._wait_for_port(container)
                if actual_port is None:
                    raise RuntimeError(f"Could not get port mapping for container {env_id}")
                
                log.debug(f"Container port mapped: {env_id} -> {actual_port}")
                
                handle = EnvHandle(
                    env_id=env_id,
                    backend_name=self.name,
                    host="127.0.0.1",
                    port=actual_port,
                    container_id=container.id,
                    metadata={"status": "starting"},
                )
                
                if self._wait_for_ready(handle):
                    handle.metadata["status"] = "ready"
                else:
                    raise RuntimeError(f"Container {env_id} failed to start within {self.STARTUP_TIMEOUT}s")
                
                self._active_handles[env_id] = handle
                handles.append(handle)
                
                log.info(f"Environment {env_id} ready on port {actual_port}")
                
            except Exception as e:
                if container:
                    log.warning(f"Cleaning up failed container {env_id}")
                    try:
                        container.stop(timeout=5)
                    except Exception:
                        pass
                    unregister_container(container.id)
                
                for h in handles:
                    self._stop_single(h)
                raise RuntimeError(f"Failed to start env {i+1}/{num_envs}: {e}")
        
        return handles

    def _wait_for_port(self, container, max_attempts: int = 10) -> Optional[int]:
        """Wait for container port mapping to be ready."""
        for _ in range(max_attempts):
            container.reload()
            port_info = container.attrs["NetworkSettings"]["Ports"]
            port_key = f"{self.CONTAINER_PORT}/tcp"
            
            if port_info and port_key in port_info and port_info[port_key]:
                return int(port_info[port_key][0]["HostPort"])
            
            time.sleep(0.5)
        return None
    
    def _stop_single(self, handle: EnvHandle) -> None:
        """Stop a single container."""
        log.debug(f"Stopping env: {handle.env_id}")
        
        if handle.container_id:
            try:
                container = self.client.containers.get(handle.container_id)
                container.stop(timeout=10)
                log.debug(f"Container stopped: {handle.container_id[:12]}")
            except NotFound:
                log.debug(f"Container already removed: {handle.container_id[:12]}")
            
            unregister_container(handle.container_id)
        
        self._active_handles.pop(handle.env_id, None)
    
    def stop(self, handles: List[EnvHandle]) -> None:
        """Stop environment containers."""
        for handle in handles:
            self._stop_single(handle)

    @retry(max_attempts=2, delay=0.5, exceptions=(requests.exceptions.ConnectionError,))
    def _post(self, url: str, json: dict = None, params: dict = None, timeout: int = 30) -> requests.Response:
        """POST request with retry logic."""
        return requests.post(url, json=json, params=params, timeout=timeout)
    
    def _handle_response(self, resp: requests.Response, operation: str) -> dict:
        """Handle HTTP response, raising on error."""
        if resp.status_code != 200:
            try:
                detail = resp.json().get("detail", resp.text)
            except Exception:
                detail = resp.text
            raise RuntimeError(f"Env container error ({resp.status_code}): {detail}")
        return resp.json()
        
    def setup(self, handle: EnvHandle, task: str, seed: Optional[int] = None) -> dict:
        """Setup environment with a specific task."""
        base_url = self._get_base_url(handle)
        log.info(f"Setting up env {handle.env_id} with task: {task}")
        
        payload = {"task": task}
        if seed is not None:
            payload["seed"] = seed
        
        try:
            resp = self._post(f"{base_url}/setup", json=payload, timeout=60)
            result = self._handle_response(resp, "setup")
            
            handle.metadata["task"] = result.get("task")
            handle.metadata["instruction"] = result.get("instruction")
            handle.metadata["status"] = "setup"
            
            log.debug(f"Env {handle.env_id} setup complete: {result.get('task')}")
            return result
            
        except requests.exceptions.RequestException as e:
            log.error(f"Failed to setup env {handle.env_id}: {e}")
            raise RuntimeError(f"Failed to setup env {handle.env_id}: {e}")
    
    def reset(self, handle: EnvHandle, seed: Optional[int] = None) -> dict:
        """Reset the environment."""
        base_url = self._get_base_url(handle)
        log.debug(f"Resetting env {handle.env_id}")
        
        params = {}
        if seed is not None:
            params["seed"] = seed
        
        try:
            resp = self._post(f"{base_url}/reset", params=params, timeout=30)
            return self._handle_response(resp, "reset")
        except requests.exceptions.RequestException as e:
            log.error(f"Failed to reset env {handle.env_id}: {e}")
            raise RuntimeError(f"Failed to reset env {handle.env_id}: {e}")
    
    def step(self, handle: EnvHandle, action: List[float]) -> dict:
        """Take a step in the environment."""
        base_url = self._get_base_url(handle)
        
        try:
            resp = requests.post(f"{base_url}/step", json={"action": action}, timeout=30)
            return self._handle_response(resp, "step")
        except requests.exceptions.RequestException as e:
            log.error(f"Failed to step env {handle.env_id}: {e}")
            raise RuntimeError(f"Failed to step env {handle.env_id}: {e}")
    
    def get_info(self, handle: EnvHandle) -> dict:
        """Get environment info."""
        base_url = self._get_base_url(handle)
        
        try:
            resp = requests.get(f"{base_url}/info", timeout=10)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.RequestException as e:
            log.error(f"Failed to get info for env {handle.env_id}: {e}")
            raise RuntimeError(f"Failed to get info for env {handle.env_id}: {e}")
        
    @abstractmethod
    def list_tasks(self, suite: Optional[str] = None) -> dict:
        """
        List available tasks. Env-specific implementation required.
        
        Args:
            suite: Optional task suite filter
            
        Returns:
            dict mapping suite names to task lists
        """
        pass

    def _get_container_config(self) -> dict:
        """
        Get container configuration. Override in subclass for custom config.
        
        Returns:
            dict with: environment, volumes, device_requests, etc.
        """
        return {
            "environment": {},
            "volumes": {},
            "device_requests": [],
        }