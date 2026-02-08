import requests
from typing import List, Optional, Any, Dict
from maple.utils.logging import get_logger
from maple.backend.policy.base import PolicyBackend, PolicyHandle

log = get_logger("policy.smolvla")

class SmolVLAPolicy(PolicyBackend):
    name = "smolvla"
    _image = "maplerobotics/smolvla:latest"
    
    _hf_repos = {
        "libero": "HuggingFaceVLA/smolvla_libero",
        "base": "lerobot/smolvla_base"
    }    
    
    _container_port: int = 8000
    _startup_timeout: int = 300
    _health_check_interval: int = 5

    def info(self) -> dict:
        return {
            "name": self.name,
            "type": "policy",
            "inputs": ["image", "state", "instruction"],
            "outputs": ["action"],
            "versions": list(self._hf_repos.keys()),
            "image": self._image,
        }

    def act(
        self, 
        handle: PolicyHandle, 
        payload: Any, 
        instruction: str,
        model_kwargs: Optional[Dict[str, Any]] = {},
    ) -> List[float]:
        """Get action for a single observation."""
        base_url = self._get_base_url(handle)
        
        observations = {}
        for key, value in payload.items():
            if "image" in key:
                observations[key] = self._encode_image(value) if not isinstance(value, str) else value
            else:
                observations[key] = value
        payload = {}
        payload["observations"] = observations
        payload["prompt"] = instruction    
        
        try:
            resp = requests.post(f"{base_url}/act", json=payload, timeout=300)
            resp.raise_for_status()
            return resp.json()["action"]
        except requests.exceptions.RequestException as e:
            log.error(f"Failed to connect to policy container: {e}")
            raise RuntimeError(f"Failed to get action: {e}")