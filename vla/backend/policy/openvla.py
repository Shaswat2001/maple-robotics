import requests
from typing import List, Optional, Any
from vla.backend.policy.base import PolicyBackend, PolicyHandle

class OpenVLAPolicy(PolicyBackend):
    name = "openvla"

    IMAGE = "shaswatai/robotics_vla:openvla"
    CONTAINER_PORT = 8000
    STARTUP_TIMEOUT = 300
    HEALTH_CHECK_INTERVAL = 5

    HF_REPOS = {
        "7b": "openvla/openvla-7b",
        "latest": "openvla/openvla-7b",
    }    

    def info(self) -> dict:
        return {
            "name": self.name,
            "type": "policy",
            "inputs": ["image", "instruction"],
            "outputs": ["action"],
            "versions": list(self.HF_REPOS.keys()),
            "image": self.IMAGE,
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
        
        try:
            resp = requests.post(f"{base_url}/act", json=payload, timeout=300)
            resp.raise_for_status()
            return resp.json()["action"]
        except requests.exceptions.RequestException as e:
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
            raise RuntimeError(f"Failed to get batch actions: {e}")
