import io
import time
import base64
import docker
import requests
import numpy as np
from PIL import Image
from pathlib import Path
from docker.errors import NotFound
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

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

    def __init__(self):
        self.client = docker.from_env()
        self._active_handles: Dict[str, PolicyHandle] = {}

    def _get_base_url(self, handle: PolicyHandle) -> str:
        """Get base URL for RPC calls."""
        return f"http://{handle.host}:{handle.port}"
    
    def wait_for_ready(self, handle: PolicyHandle) -> bool:
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
        return base64.b64decode(buffer.getvalue()).decode("utf-8")

    @abstractmethod
    def info(self) -> dict:
        pass

    @abstractmethod
    def pull(self, version: str, dst: Path) -> dict:
        """Download model artifacts into dst"""
        pass

    @abstractmethod
    def serve(self, 
              version: str, 
              model_path: Path, 
              device: str, 
              host_port: Optional[int] = None,
              attn_implementation: str = "sdpa") -> PolicyHandle:
        
        pass

    def stop(self, handle: PolicyHandle) -> None:
        if handle.container_id:
            try:
                container = self.client.containers.get(handle.container_id)
                container.stop(timeout=10)
            except NotFound:
                pass
        
        if handle.policy_id in self._active_handles:
            del self._active_handles[handle.policy_id]

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

    def get_info(self, handle: PolicyHandle) -> dict:
        """Get info about a running policy instance."""
        base_url = self._get_base_url(handle)
        
        try:
            resp = requests.get(f"{base_url}/info", timeout=10)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Failed to get policy info: {e}")
    
    def health(self, handle: PolicyHandle) -> dict:
        """Check health of a policy instance."""
        base_url = self._get_base_url(handle)
        
        try:
            resp = requests.get(f"{base_url}/health", timeout=5)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.RequestException as e:
            return {"status": "error", "error": str(e)}

