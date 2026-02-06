"""
OpenVLA policy backend.

This module implements the policy backend for OpenVLA (Open Vision-Language-Action),
a vision-language-action model for robotic manipulation. OpenVLA takes visual
observations and natural language instructions as input and outputs robot actions.

OpenVLA is based on transformer architectures and requires action unnormalization
using dataset statistics to produce executable robot commands. The model is
served via Docker containers with the inference API accessible over HTTP.

Available versions:
- 7b: OpenVLA 7B parameter model
- latest: Alias for the 7B model (default)
"""

import requests
from typing import List, Optional, Any, Dict

from maple.utils.logging import get_logger
from maple.backend.policy.base import PolicyBackend, PolicyHandle

log = get_logger("policy.openvla")

class OpenVLAPolicy(PolicyBackend):
    """
    Backend for OpenVLA vision-language-action models.
    
    OpenVLA is a generalist robot policy that conditions on visual observations
    and natural language instructions to predict robot actions. The model requires
    dataset-specific statistics for action unnormalization to convert normalized
    model outputs into executable robot commands.
    
    The backend manages Docker containers running the OpenVLA inference server,
    which loads the model from HuggingFace and serves predictions via HTTP API.
    """
    
    name = "openvla"
    _image = "maplerobotics/openvla:latest"
    
    # Map version strings to HuggingFace repository paths
    _hf_repos = {
        "7b": "openvla/openvla-7b",
        "latest": "openvla/openvla-7b",
    }
    
    _container_port: int = 8000
    _startup_timeout: int = 300  # Model loading can take several minutes
    _health_check_interval: int = 5

    def info(self) -> Dict:
        """
        Get policy backend information and capabilities.
        
        Returns metadata about the OpenVLA policy including supported inputs,
        outputs, available versions, and Docker image information.
        
        :return: Dictionary with policy metadata including name, type, inputs,
                outputs, versions, and image.
        """
        return {
            "name": self.name,
            "type": "policy",
            "inputs": ["image", "instruction"],  # Required inputs for inference
            "outputs": ["action"],  # Model produces action vectors
            "versions": list(self._hf_repos.keys()),  # Available model versions
            "image": self._image,  # Docker image used for serving
        }

    def act(
        self, 
        handle: PolicyHandle, 
        payload: Any, 
        instruction: str,
        model_kwargs: Optional[Dict[str, Any]] = {},
    ) -> List[float]:
        """
        Get action prediction for a single observation.
        
        Sends a visual observation and language instruction to the OpenVLA
        model and receives a predicted action. The action is unnormalized
        using dataset statistics specified by unnorm_key.
        
        IMPORTANT: OpenVLA requires unnorm_key to be specified. The model
        outputs normalized actions that must be converted to the target
        action space using dataset-specific statistics. Without unnormalization,
        the actions cannot be executed on real robots or simulators.
        
        :param handle: Policy handle for the running container.
        :param payload: Observation payload containing 'image' key with image data.
        :param instruction: Natural language instruction for the task.
        :param model_kwargs: Model-specific parameters. Must contain 'unnorm_key'. (REQUIRED).
                          Examples: 'libero_spatial', 'bridge', 'fractal'.
        :return: Predicted action as list of floats, unnormalized to target space.
        """
        # Get base URL for container communication
        base_url = self._get_base_url(handle)
        
        # Build request payload with encoded image and instruction
        payload = {
            "image": self._encode_image(payload["image"]),  # Base64 encode image
            "instruction": instruction,
        }
        
        unnorm_key = model_kwargs.get("unnorm_key", None)
        # Validate unnorm_key is provided (required for OpenVLA)
        if unnorm_key:
            payload["unnorm_key"] = unnorm_key
        else:
            # OpenVLA cannot produce executable actions without unnormalization
            log.error(f"Error: In OpenVLA unnorm_key can't be None")
            raise RuntimeError(f"In OpenVLA unnorm_key can't be None")
        
        try:
            # Send inference request with generous timeout (inference can be slow)
            resp = requests.post(f"{base_url}/act", json=payload, timeout=300)
            resp.raise_for_status()
            
            # Extract action from response
            return resp.json()["action"]
            
        except requests.exceptions.RequestException as e:
            log.error(f"Failed to connect to policy container: {e}")
            raise RuntimeError(f"Failed to get action: {e}")