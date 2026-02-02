import requests
from typing import List, Optional, Any
from maple.utils.logging import get_logger
from maple.backend.policy.base import PolicyBackend, PolicyHandle

log = get_logger("policy.openvla")


class OpenVLAPolicy(PolicyBackend):
    name = "openvla"
    _image = "shaswatai/robotics_vla:openvla"
    _hf_repos = {
        "7b": "openvla/openvla-7b",
        "latest": "openvla/openvla-7b",
    }    
    
    _container_port: int = 8000
    _startup_timeout: int = 300
    _health_check_interval: int = 5

    def info(self) -> dict:
        return {
            "name": self.name,
            "type": "policy",
            "inputs": ["image", "instruction"],
            "outputs": ["action"],
            "versions": list(self._hf_repos.keys()),
            "image": self._image,
        }

    def act(
        self, 
        handle: PolicyHandle, 
        payload: Any, 
        instruction: str,
        unnorm_key: Optional[str] = None,
    ) -> List[float]:
        """Get action for a single observation."""
        base_url = self._get_base_url(handle)
        
        payload = {
            "image": self._encode_image(payload["image"]),
            "instruction": instruction,
        }
        if unnorm_key:
            payload["unnorm_key"] = unnorm_key
        else:
            log.error(f"Error: In OpenVLA unnorm_key can't be None")
            raise RuntimeError(f"In OpenVLA unnorm_key can't be None")
        
        try:
            resp = requests.post(f"{base_url}/act", json=payload, timeout=300)
            resp.raise_for_status()
            return resp.json()["action"]
        except requests.exceptions.RequestException as e:
            log.error(f"Failed to connect to policy container: {e}")
            raise RuntimeError(f"Failed to get action: {e}")
    
    def act_batch(
        self,
        handle: PolicyHandle,
        images: List[Any],
        instructions: List[str],
        unnorm_key: Optional[str] = None
    ) -> List[List[float]]:
        """Get actions for a batch of observations."""
        base_url = self._get_base_url(handle)
        
        payload = {
            "images": [self._encode_image(img) for img in images],
            "instructions": instructions,
        }
        if unnorm_key:
            payload["unnorm_key"] = unnorm_key
        
        try:
            resp = requests.post(f"{base_url}/act_batch", json=payload, timeout=60)
            resp.raise_for_status()
            return resp.json()["actions"]
        except requests.exceptions.RequestException as e:
            log.error(f"Failed to connect to policy container: {e}")
            raise RuntimeError(f"Failed to get batch actions: {e}")
