"""
SmolVLA policy backend.

This module implements the policy backend for SmolVLA (Small Vision-Language-Action),
a compact vision-language-action model for robotic manipulation. SmolVLA takes visual
observations, proprioceptive state, and natural language instructions as input and 
outputs robot actions.

SmolVLA is based on transformer architectures and supports multiple observation
modalities including images and robot state. Unlike OpenVLA, SmolVLA does not require
explicit action unnormalization as it directly outputs actions in the target space.
The model is served via Docker containers with the inference API accessible over HTTP.

Available versions:
- libero: SmolVLA fine-tuned for LIBERO benchmark tasks
- base: Base SmolVLA model trained on diverse robot datasets
"""

import requests
from typing import List, Optional, Any, Dict

from maple.utils.logging import get_logger
from maple.backend.policy.base import PolicyBackend, PolicyHandle

log = get_logger("policy.smolvla")

class SmolVLAPolicy(PolicyBackend):
    """
    Backend for SmolVLA vision-language-action models.
    
    SmolVLA is a compact generalist robot policy that conditions on visual observations,
    proprioceptive state, and natural language instructions to predict robot actions.
    The model handles multi-modal observations including multiple camera views and
    robot state information, making it suitable for complex manipulation tasks.
    
    The backend manages Docker containers running the SmolVLA inference server,
    which loads the model from HuggingFace and serves predictions via HTTP API.
    """
    
    name = "smolvla"
    _image = "maplerobotics/smolvla:latest"
    
    # Map version strings to HuggingFace repository paths
    _hf_repos = {
        "libero": "HuggingFaceVLA/smolvla_libero",  # LIBERO benchmark version
        "base": "lerobot/smolvla_base"              # Base multi-task version
    }
    
    _container_port: int = 8000
    _startup_timeout: int = 300  # Model loading can take several minutes
    _health_check_interval: int = 5

    def info(self) -> dict:
        """
        Get policy backend information and capabilities.
        
        Returns metadata about the SmolVLA policy including supported inputs,
        outputs, available versions, and Docker image information.
        
        :return: Dictionary with policy metadata including name, type, inputs,
                outputs, versions, and image.
        """
        return {
            "name": self.name,
            "type": "policy",
            "inputs": ["image", "state", "instruction"],  # Required inputs for inference
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
        
        Sends visual observations, proprioceptive state, and language instruction
        to the SmolVLA model and receives a predicted action. 
                
        :param handle: Policy handle for the running container.
        :param payload: Observation payload containing image and state keys.
                       Image keys are automatically detected and base64 encoded.
                       Non-image keys (e.g., 'state') are passed through directly.
        :param instruction: Natural language instruction for the task.
        :param model_kwargs: Model-specific parameters (optional for SmolVLA).
        :return: Predicted action as list of floats in the target action space.
        """
        # Get base URL for container communication
        base_url = self._get_base_url(handle)
        
        # Process observations: encode images, pass through other data
        observations = {}
        for key, value in payload.items():
            if "image" in key:
                # Base64 encode image data unless already encoded
                observations[key] = self._encode_image(value) if not isinstance(value, str) else value
            else:
                # Pass through non-image data (e.g., robot state)
                observations[key] = value
        
        # Build request payload with observations and instruction
        payload = {}
        payload["observations"] = observations
        payload["instruction"] = instruction
        
        try:
            # Send inference request with generous timeout (inference can be slow)
            resp = requests.post(f"{base_url}/act", json=payload, timeout=300)
            resp.raise_for_status()
            
            # Extract action from response
            return resp.json()["action"]
            
        except requests.exceptions.RequestException as e:
            log.error(f"Failed to connect to policy container: {e}")
            raise RuntimeError(f"Failed to get action: {e}")