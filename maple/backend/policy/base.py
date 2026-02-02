import io
import uuid
import time
import base64
import docker
import requests
import numpy as np
from PIL import Image
from pathlib import Path
from docker.errors import NotFound, APIError
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from huggingface_hub import snapshot_download

from maple.utils.retry import retry
from maple.utils.logging import get_logger
from maple.config import config as maple_config
from maple.utils.cleanup import register_container, unregister_container

log = get_logger("policy.base")

def _get_config_value(attr: str, default: Any) -> Any:
    """Get config value, falling back to default if config not loaded."""
    try:
        if attr == "memory_limit":
            return maple_config.containers.memory_limit
        elif attr == "shm_size":
            return maple_config.containers.shm_size
        elif attr == "startup_timeout":
            return maple_config.containers.startup_timeout
        elif attr == "health_check_interval":
            return maple_config.containers.health_check_interval
    except Exception:
        pass
    return default

@dataclass
class PolicyHandle:

    policy_id: str
    backend_name: str
    version: str
    host: str
    port: int
    container_id: Optional[str] = None
    model_path: Optional[str] = None
    device: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "policy_id": self.policy_id,
            "backend_name": self.backend_name,
            "version": self.version,
            "host": self.host,
            "port": self.port,
            "container_id": self.container_id,
            "model_path": self.model_path,
            "device": self.device,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, d: Dict) -> "PolicyHandle":
        return cls(**d)
    
class PolicyBackend(ABC):
    name: str
    _image: str
    _hf_repos: Dict[str, str]  # version -> HuggingFace repo ID
    
    _container_port: int = 8000
    _startup_timeout: int = 300
    _health_check_interval: int = 5
    _memory_limit: str = "32g"
    _shm_size: str = "2g"

    def __init__(self):
        self.client = docker.from_env()
        self._active_handles: Dict[str, PolicyHandle] = {}

        self._memory_limit = _get_config_value("memory_limit", self._memory_limit)
        self._shm_size = _get_config_value("shm_size", self._shm_size)
        self._startup_timeout = _get_config_value("startup_timeout", self._startup_timeout)
        self._health_check_interval = _get_config_value("health_check_interval", self._health_check_interval)

    @abstractmethod
    def info(self) -> dict:
        pass
    
    @abstractmethod
    def act(self, handle: PolicyHandle, image: Any, instruction: str, unnorm_key: Optional[str] = None) -> List[float]:
        pass

    @abstractmethod
    def act_batch(self, 
        handle: PolicyHandle, 
        images: List[Any], 
        instructions: List[str],
        unnorm_key: Optional[str] = None) -> List[List[float]]:
        pass

    def _get_base_url(self, handle: PolicyHandle) -> str:
        """Get base URL for RPC calls."""
        return f"http://{handle.host}:{handle.port}"
    
    def wait_for_ready(self, handle: PolicyHandle) -> bool:
        base_url = self._get_base_url(handle)
        deadline = time.time() + self._startup_timeout

        log.debug(f"Waiting for container {handle.policy_id} to be ready...")

        while time.time() < deadline:
            try:
                resp = requests.get(f"{base_url}/health", timeout=5)
                if resp.status_code == 200:
                    log.debug(f"Container {handle.policy_id} is ready")
                    return True
            except requests.exceptions.ConnectionError:
                pass
            except requests.exceptions.Timeout:
                pass
            
            time.sleep(self._health_check_interval)
        
        log.error(f"Container {handle.policy_id} failed to become ready within {self._startup_timeout}s")
        return False
    
    def _encode_image(self, image: Any) -> str:

        if isinstance(image, str):
            return image
        
        if isinstance(image, np.ndarray):
            if image.dtype != np.uint8:
                image = (image * 255).astype(np.uint8)
            image = Image.fromarray(image)
        elif isinstance(image, Image.Image):
            image = image
        else:
            raise ValueError(f"Unsupported image type: {type(image)}")
        
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return base64.b64encode(buffer.getvalue()).decode("utf-8")

    def serve(self,
              version: str,
              model_path: Path,
              device: str,
              host_port: Optional[int] = None,
              attn_implementation: str = "sdpa") -> PolicyHandle:
        
        policy_id = f"openvla-{version}-{uuid.uuid4().hex[:8]}"

        log.info(f"Starting policy container: {policy_id}")
        log.debug(f"  Model path: {model_path}")
        log.debug(f"  Device: {device}")
        log.debug(f"  Attention: {attn_implementation}")

        if host_port is not None:
            port_mapping = {f"{self._container_port}/tcp": host_port}
        else:
            port_mapping = {f"{self._container_port}/tcp": None}

        config = self._get_container_config(device, attn_implementation)

        container = None
        try:
            container = self.client.containers.run(
                self._image,
                detach=True,
                remove=True,
                name=policy_id,
                ports=port_mapping,
                volumes={
                    str(model_path.absolute()): {
                        "bind": "/models/weights",
                        "mode": "ro",
                    }
                },
                device_requests=config.get("device_requests", []),
                environment=config.get("environment", {}),
                labels={
                    "vla.policy": self.name,
                    "vla.policy_id": policy_id,
                    "vla.version": version,
                },
                mem_limit=self._memory_limit,
                shm_size=self._shm_size,
            )

            register_container(container.id, policy_id)
            log.debug(f"Container started: {container.id[:12]}")
            
            # Wait for port mapping
            actual_port = self._wait_for_port(container)
            if actual_port is None:
                raise RuntimeError(f"Could not get port mapping for container {policy_id}")
            
            log.debug(f"Container port mapped: {actual_port}")
            
            handle = PolicyHandle(
                policy_id=policy_id,
                backend_name=self.name,
                version=version,
                host="127.0.0.1",
                port=actual_port,
                container_id=container.id,
                model_path=str(model_path),
                device=device,
                metadata={
                    "status": "starting",
                    "attn_implementation": attn_implementation,
                },
            )
            
            # Wait for container to be ready
            if not self._wait_for_ready(handle):
                raise RuntimeError(f"Container {policy_id} failed to start within {self._startup_timeout}s")
            
            # Load model
            self._load_model(handle, device, attn_implementation)
            
            handle.metadata["status"] = "ready"
            self._active_handles[policy_id] = handle
            
            log.info(f"Policy {policy_id} ready on port {actual_port}")
            return handle
            
        except Exception as e:
            if container:
                log.warning(f"Cleaning up failed container {policy_id}")
                try:
                    container.stop(timeout=5)
                except Exception:
                    pass
                unregister_container(container.id)
            raise RuntimeError(f"Failed to serve policy: {e}")

    def _wait_for_port(self, container, max_attempts: int = 10) -> Optional[int]:
        """Wait for container port mapping to be ready."""
        for _ in range(max_attempts):
            container.reload()
            port_info = container.attrs["NetworkSettings"]["Ports"]
            port_key = f"{self._container_port}/tcp"
            
            if port_info and port_key in port_info and port_info[port_key]:
                return int(port_info[port_key][0]["HostPort"])
            
            time.sleep(0.5)
        return None
    
    def _load_model(self, handle: PolicyHandle, device: str, attn_implementation: str):
        """Load model inside the container."""
        base_url = self._get_base_url(handle)
        
        log.info(f"Loading model on {device} with {attn_implementation} attention...")
        
        resp = requests.post(
            f"{base_url}/load",
            json={
                "model_path": "/models/weights",
                "device": device,
                "attn_implementation": attn_implementation,
            },
            timeout=self._startup_timeout,
        )
        
        if resp.status_code != 200:
            error_detail = resp.json().get('detail', resp.text) if resp.text else "Unknown error"
            raise RuntimeError(f"Failed to load model: {error_detail}")
    
    def stop(self, handle: PolicyHandle) -> None:
        """Stop a running policy container."""
        log.info(f"Stopping policy: {handle.policy_id}")
        
        if handle.container_id:
            try:
                container = self.client.containers.get(handle.container_id)
                container.stop(timeout=10)
                log.debug(f"Container stopped: {handle.container_id[:12]}")
            except NotFound:
                log.debug(f"Container already removed: {handle.container_id[:12]}")
            
            unregister_container(handle.container_id)
        
        self._active_handles.pop(handle.policy_id, None)

    def get_info(self, handle: PolicyHandle) -> dict:
        """Get info about a running policy instance."""
        base_url = self._get_base_url(handle)
        
        try:
            resp = requests.get(f"{base_url}/info", timeout=10)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.RequestException as e:
            log.error(f"Failed to get policy info: {e}")
            raise RuntimeError(f"Failed to get policy info: {e}")
        
    def pull_image(self) -> dict:
        """Pull or check for the Docker image."""
        try:
            log.info(f"Pulling Docker image {self._image}...")
            self.client.images.pull(self._image)
            log.info(f"Image pulled: {self._image}")
            return {"image": self._image, "source": "pulled"}
        except APIError:
            pass
        
        try:
            self.client.images.get(self._image)
            log.debug(f"Image found locally: {self._image}")
            return {"image": self._image, "source": "local"}
        except NotFound:
            raise RuntimeError(
                f"Image {self._image} not found. "
                f"Build it with: docker build -t {self._image} docker/{self.name}/"
            )
        
    def pull(self, version: str, dst: Path) -> dict:
        repo = self._hf_repos.get(version)
        if repo is None:
            raise ValueError(f"Unknown version '{version}' for {self.name}")

        dst.mkdir(parents=True, exist_ok=True)

        self.pull_image()

        log.info(f"Downloading {repo} to {dst}...")

        snapshot_download(
            repo_id=repo,
            local_dir=dst,
        )

        log.info(f"Download complete: {repo}")

        return {
            "name": self.name,
            "version": version,
            "source": "huggingface",
            "repo": repo,
            "path": str(dst),
        }
    
    def health(self, handle: PolicyHandle) -> dict:
        """Check health of a policy instance."""
        base_url = self._get_base_url(handle)
        
        try:
            resp = requests.get(f"{base_url}/health", timeout=5)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.RequestException as e:
            log.warning(f"Health check failed for {handle.policy_id}: {e}")
            return {"status": "error", "error": str(e)}

    def _get_container_config(self, device: str, attn_implementation: str) -> dict:
        """
        Get container configuration. Override in subclass for custom config.
        
        Returns:
            dict with: environment, volumes, device_requests
        """
        gpu_idx = "0"
        device_requests = []
        
        if device.startswith("cuda"):
            gpu_idx = device.split(":")[-1] if ":" in device else "0"
            device_requests = [
                docker.types.DeviceRequest(
                    device_ids=[gpu_idx],
                    capabilities=[["gpu"]]
                )
            ]
        
        return {
            "environment": {
                "CUDA_VISIBLE_DEVICES": gpu_idx if device.startswith("cuda") else "",
                "ATTN_IMPLEMENTATION": attn_implementation,
            },
            "device_requests": device_requests,
        }
    
    @retry(max_attempts=3, delay=0.5, exceptions=(requests.exceptions.ConnectionError, requests.exceptions.Timeout))
    def _post_with_retry(self, url: str, json: dict, timeout: int) -> requests.Response:
        """POST request with retry logic."""
        return requests.post(url, json=json, timeout=timeout)
    
    def _handle_response(self, resp: requests.Response, operation: str) -> dict:
        """Handle HTTP response, raising detailed error on failure."""
        if resp.status_code != 200:
            try:
                detail = resp.json().get("detail", resp.text)
            except Exception:
                detail = resp.text
            log.error(f"Policy container error: {detail}")
            raise RuntimeError(f"Policy container error ({resp.status_code}): {detail}")
        return resp.json()
    
    def _wait_for_ready(self, handle: PolicyHandle) -> bool:
        """Wait for container to be ready to accept requests."""
        base_url = self._get_base_url(handle)
        deadline = time.time() + self._startup_timeout
        
        log.debug(f"Waiting for container {handle.policy_id} to be ready...")
        
        while time.time() < deadline:
            try:
                resp = requests.get(f"{base_url}/health", timeout=10)
                if resp.status_code == 200:
                    log.debug(f"Container {handle.policy_id} is ready")
                    return True
            except requests.exceptions.ConnectionError:
                pass
            except requests.exceptions.Timeout:
                pass
            
            time.sleep(self._health_check_interval)
        
        log.error(f"Container {handle.policy_id} failed to become ready within {self._startup_timeout}s")
        return False