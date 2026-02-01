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
from maple.utils.cleanup import register_container, unregister_container

log = get_logger("policy.base")

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
    IMAGE: str
    HF_REPOS: Dict[str, str]  # version -> HuggingFace repo ID
    
    CONTAINER_PORT: int = 8000
    STARTUP_TIMEOUT: int = 300
    HEALTH_CHECK_INTERVAL: int = 5
    MEMORY_LIMIT: str = "32g"
    SHM_SIZE: str = "2g"

    def __init__(self):
        self.client = docker.from_env()
        self._active_handles: Dict[str, PolicyHandle] = {}

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
        deadline = time.time() + self.STARTUP_TIMEOUT

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
            
            time.sleep(self.HEALTH_CHECK_INTERVAL)
        
        log.error(f"Container {handle.policy_id} failed to become ready within {self.STARTUP_TIMEOUT}s")
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
            port_mapping = {f"{self.CONTAINER_PORT}/tcp": host_port}
        else:
            port_mapping = {f"{self.CONTAINER_PORT}/tcp": None}

        config = self._get_container_config(device, attn_implementation)

        try:
            container = self.client.containers.run(
                self.IMAGE,
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
                mem_limit=self.MEMORY_LIMIT,
                shm_size=self.SHM_SIZE,
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
                raise RuntimeError(f"Container {policy_id} failed to start within {self.STARTUP_TIMEOUT}s")
            
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
            port_key = f"{self.CONTAINER_PORT}/tcp"
            
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
            timeout=self.STARTUP_TIMEOUT,
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
            log.info(f"Pulling Docker image {self.IMAGE}...")
            self.client.images.pull(self.IMAGE)
            log.info(f"Image pulled: {self.IMAGE}")
            return {"image": self.IMAGE, "source": "pulled"}
        except APIError:
            pass
        
        try:
            self.client.images.get(self.IMAGE)
            log.debug(f"Image found locally: {self.IMAGE}")
            return {"image": self.IMAGE, "source": "local"}
        except NotFound:
            raise RuntimeError(
                f"Image {self.IMAGE} not found. "
                f"Build it with: docker build -t {self.IMAGE} docker/{self.name}/"
            )
        
    def pull(self, version: str, dst: Path) -> dict:
        repo = self.HF_REPOS.get(version)
        if repo is None:
            raise ValueError(f"Unknown version '{version}' for {self.name}")

        dst.mkdir(parents=True, exist_ok=True)

        self.pull_image()

        log.info(f"Downloading {repo} to {dst}...")

        snapshot_download(
            repo_id=repo,
            local_dir=dst,
            local_dir_use_symlinks=False,
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
        deadline = time.time() + self.STARTUP_TIMEOUT
        
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
            
            time.sleep(self.HEALTH_CHECK_INTERVAL)
        
        log.error(f"Container {handle.policy_id} failed to become ready within {self.STARTUP_TIMEOUT}s")
        return False