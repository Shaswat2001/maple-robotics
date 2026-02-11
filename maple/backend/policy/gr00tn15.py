"""
GR00T N1.5/N1.6 policy backend.

This module implements the policy backend for NVIDIA Isaac GR00T N1.5/N1.6,
a foundation model for generalized humanoid robot reasoning and skills.
GR00T takes visual observations, proprioceptive state, and natural
language instructions as input and outputs robot actions using a flow
matching transformer architecture.

GR00T is a cross-embodiment model that can be post-trained for specific
robot platforms. It uses SigLip2 for vision encoding, T5 for text encoding,
and a flow matching diffusion transformer for action prediction.

Available versions:
- 3b: GR00T N1.5 3B parameter model
- n1.5-3b: GR00T N1.5 3B parameter model  
- n1.6-3b: GR00T N1.6 3B parameter model (latest)
- latest: Alias for the N1.6 3B model

Supported embodiments and data configs:
- GR1: fourier_gr1_arms_only (Fourier GR1 humanoid)
- LIBERO: libero (LIBERO benchmark tasks)
- ALOHA: aloha, aloha_2 (Aloha bimanual)
- SO100: so100_dualcam (SO-100/SO-101 arms)
- OXE_DROID: oxe_droid (Open X-Embodiment DROID)
"""

import requests
from typing import List, Optional, Any, Dict

from maple.utils.logging import get_logger
from maple.utils.misc import parse_error_response
from maple.backend.policy.base import PolicyBackend, PolicyHandle

log = get_logger("policy.gr00tn15")

class GR00TN15Policy(PolicyBackend):
    """
    Backend for NVIDIA Isaac GR00T N1.5/N1.6 vision-language-action models.
    
    GR00T is an open foundation model for generalized humanoid robot reasoning
    and skills. It is a cross-embodiment model that takes multimodal input 
    including language, images, and proprioception to perform manipulation 
    tasks in diverse environments.
    
    Key features:
    - Flow matching transformer for action prediction
    - Cross-embodiment support via EmbodimentTag system
    - Multi-camera view support
    - Proprioceptive state conditioning
    - Action chunk prediction (default horizon: 16)
    
    The backend manages Docker containers running the GR00T inference server,
    which loads the model from HuggingFace and serves predictions via HTTP API.
    
    Model Load Kwargs:
    - embodiment_tag: Robot embodiment identifier (e.g., 'GR1', 'NEW_EMBODIMENT')
    - data_config: Data configuration name (e.g., 'fourier_gr1_arms_only', 'libero')
    - denoising_steps: Number of flow matching denoising steps (default: 4)
    """
    
    name = "groot"
    _image = "maplerobotics/gr00tn1.5:latest"
    
    # Map version strings to HuggingFace repository paths
    _hf_repos = {
        "libero_spatial": "Tacoin/GR00T-N1.5-3B-LIBERO-SPATIAL",
    }

    _embodiment_tags = {
        "libero_spatial": "new_embodiment"
    }

    _data_configs = {
        "libero_spatial": "examples.Libero.custom_data_config:LiberoDataConfig"
    }
    
    _container_port: int = 8000
    _startup_timeout: int = 600  # GR00T model loading can take longer
    _health_check_interval: int = 5

    def info(self) -> Dict:
        """
        Get policy backend information and capabilities.
        
        Returns metadata about the GR00T policy including supported inputs,
        outputs, available versions, embodiments, and data configs.
        
        :return: Dictionary with policy metadata.
        """
        return {
            "name": self.name,
            "type": "policy",
            "inputs": ["image", "state", "instruction"],
            "outputs": ["action"],
            "versions": list(self._hf_repos.keys()),
            "image": self._image,
            "description": "NVIDIA Isaac GR00T - Foundation model for humanoid robots",
            "action_horizon": 16,
        }
    
    def _resolve_model_load_kwargs(
        self, 
        version: str, 
        model_load_kwargs: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Resolve model_load_kwargs using version defaults or user overrides.
        
        Priority:
        1. User-provided values in model_load_kwargs
        2. Version-specific defaults from class attributes
        
        :param version: Model version string
        :param model_load_kwargs: User-provided kwargs (may be None or partial)
        :return: Complete model_load_kwargs dict
        """
        if model_load_kwargs is None:
            model_load_kwargs = {}
        
        resolved = {}
        
        # Resolve embodiment_tag
        embodiment_tag = model_load_kwargs.get("embodiment_tag")
        if not embodiment_tag:
            embodiment_tag = self._embodiment_tags.get(version)
            if not embodiment_tag:
                raise ValueError(
                    f"embodiment_tag required for GR00T version: {version}. "
                    f"Available versions with defaults: {list(self._embodiment_tags.keys())}"
                )
        resolved["embodiment_tag"] = embodiment_tag
        
        # Resolve data_config
        data_config = model_load_kwargs.get("data_config")
        if not data_config:
            data_config = self._data_configs.get(version)
            if not data_config:
                raise ValueError(
                    f"data_config required for GR00T version: {version}. "
                    f"Available versions with defaults: {list(self._data_configs.keys())}"
                )
        resolved["data_config"] = data_config
        
        return resolved
    
    def _load_model(
        self,
        handle: PolicyHandle,
        device: str,
        model_load_kwargs: Optional[Dict[str, Any]] = {}
    ) -> None:
        """
        Load Gr00t N1.5 model into container memory.
        
        Sends a load request to the inference server with the model path,
        device specification, and configuration name. Gr00t N1.5 requires a
        config_name to identify which model variant to initialize.
        
        :param handle: Policy handle for the running container.
        :param device: Device to load model on ('cuda', 'cuda:0', 'cpu', etc.).
        :param model_load_kwargs: Model loading parameters. If 'config_name' is
                                 not provided, it will be inferred from handle.version.
        :raises ValueError: If config_name cannot be determined for the version.
        :raises RuntimeError: If model loading fails on the server.
        """
        base_url = self._get_base_url(handle)
        
        model_load_kwargs = self._resolve_model_load_kwargs(handle.version, model_load_kwargs)
        log.info(f"Loading Gr00t N1.5 model: {model_load_kwargs} on {device}")
        
        # Send load request to inference server
        resp = requests.post(
            f"{base_url}/load",
            json={
                "model_path": "/models/weights",  # Container-internal path
                "device": device,
                "model_load_kwargs": model_load_kwargs,
            },
            timeout=self._startup_timeout,
        )
        
        if resp.status_code != 200:
            raise RuntimeError(f"Failed to load model: {parse_error_response(resp)}")

    def act(
        self, 
        handle: PolicyHandle, 
        payload: Any, 
        instruction: str,
        model_kwargs: Optional[Dict[str, Any]] = None,
    ) -> List[float]:
        """
        Get action prediction for a single observation.
        
        Sends visual observations, proprioceptive state, and language instruction
        to the GR00T model and receives a predicted action. GR00T uses
        flow matching to iteratively denoise actions from gaussian noise.
        
        The server expects observations in the format:
        - observation.images.*: Base64 encoded camera images
        - observation.state: Robot proprioceptive state as list
        - prompt: Natural language instruction
        
        :param handle: Policy handle for the running container.
        :param payload: Observation payload containing:
                       - Image keys (e.g., 'image', 'wrist_image'): camera observations
                       - 'state' or 'observation.state': robot proprioceptive state
        :param instruction: Natural language instruction for the task.
        :param model_kwargs: Optional runtime parameters (not used for GR00T,
                           configuration is done at load time via model_load_kwargs)
        :return: Predicted action as list of floats.
        """
        if model_kwargs is None:
            model_kwargs = {}
            
        base_url = self._get_base_url(handle)
        
        # Process observations: encode images, pass through state data
        observations = {}
        for key, value in payload.items():
            # Normalize key names to GR00T format
            normalized_key = key
            if not key.startswith("observation."):
                if "image" in key.lower():
                    normalized_key = f"observation.images.{key}"
                elif key == "state":
                    normalized_key = "observation.state"
            
            if "image" in key.lower():
                # Base64 encode image data
                observations[normalized_key] = self._encode_image(value) if not isinstance(value, str) else value
            else:
                # Pass through non-image data (e.g., robot state/proprioception)
                # Convert numpy arrays or lists to plain lists
                if hasattr(value, 'tolist'):
                    observations[normalized_key] = value.tolist()
                elif isinstance(value, list):
                    observations[normalized_key] = value
                else:
                    observations[normalized_key] = value
        
        # Build request payload matching server's ActRequest schema
        request_payload = {
            "observations": observations,
            "prompt": instruction,
        }
        
        try:
            # Send inference request with generous timeout
            # GR00T uses iterative denoising which can be slower
            resp = requests.post(f"{base_url}/act", json=request_payload, timeout=300)
            resp.raise_for_status()
            
            result = resp.json()
            
            # Server returns {"action": [...]}
            if "action" in result:
                action = result["action"]
                # Handle numpy array serialization
                if hasattr(action, 'tolist'):
                    return action.tolist()
                return action
            else:
                raise RuntimeError(f"Unexpected response format: {result}")
            
        except requests.exceptions.RequestException as e:
            log.error(f"Failed to connect to policy container: {e}")
            raise RuntimeError(f"Failed to get action: {e}")
