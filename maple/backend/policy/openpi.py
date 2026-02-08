"""
OpenPI policy backend.

This module implements the policy backend for OpenPI (π₀ / π₀.₅),
Physical Intelligence's vision-language-action models for robotic manipulation.
OpenPI takes visual observations, proprioceptive state, and natural language
instructions as input and outputs robot actions.

OpenPI models are downloaded from the public S3 bucket gs://openpi-assets
using fsspec with anonymous access (no credentials required). The models
support both base versions for fine-tuning and pre-trained versions for
specific datasets including DROID, ALOHA, and LIBERO.

Available versions:
- Base models: pi0_base, pi0_fast_base, pi05_base (for fine-tuning)
- DROID: pi0_fast_droid, pi0_droid, pi05_droid (mobile manipulation)
- ALOHA: pi0_aloha_towel, pi0_aloha_tupperware, pi0_aloha_pen_uncap (bimanual tasks)
- LIBERO: pi05_libero (long-horizon manipulation benchmark)
- latest: Alias for pi05_droid (default)
"""

import shutil
from pathlib import Path
from typing import List, Optional, Any, Dict
import requests

from maple.utils.logging import get_logger
from maple.utils.misc import parse_error_response
from maple.backend.policy.base import PolicyBackend, PolicyHandle

log = get_logger("policy.openpi")

class OpenPIPolicy(PolicyBackend):
    """
    Backend for OpenPI (π₀ / π₀.₅) vision-language-action models.
    
    OpenPI is Physical Intelligence's family of generalist robot policies that
    condition on visual observations, proprioceptive state, and natural language
    instructions to predict robot actions. The models support multiple observation
    modalities and are available in different sizes (π₀ and π₀.₅) and variants
    (base, fast, task-specific fine-tunes).
    
    The backend manages Docker containers running the OpenPI inference server,
    downloads model weights from public S3 storage using fsspec with anonymous
    access, and serves predictions via HTTP API.
    """
    
    name = "openpi"
    _image = "maplerobotics/openpi:latest"
    
    # Map version strings to S3 checkpoint paths (public bucket, anonymous access)
    _gs_checkpoints = {
        # Base models (for fine-tuning)
        "pi0_base": "gs://openpi-assets/checkpoints/pi0_base",
        "pi0_fast_base": "gs://openpi-assets/checkpoints/pi0_fast_base",
        "pi05_base": "gs://openpi-assets/checkpoints/pi05_base",
        
        # DROID fine-tuned models (mobile manipulation)
        "pi0_fast_droid": "gs://openpi-assets/checkpoints/pi0_fast_droid",
        "pi0_droid": "gs://openpi-assets/checkpoints/pi0_droid",
        "pi05_droid": "gs://openpi-assets/checkpoints/pi05_droid",
        
        # ALOHA fine-tuned models (bimanual manipulation)
        "pi0_aloha_towel": "gs://openpi-assets/checkpoints/pi0_aloha_towel",
        "pi0_aloha_tupperware": "gs://openpi-assets/checkpoints/pi0_aloha_tupperware",
        "pi0_aloha_pen_uncap": "gs://openpi-assets/checkpoints/pi0_aloha_pen_uncap",
        
        # LIBERO fine-tuned model (long-horizon benchmark)
        "pi05_libero": "gs://openpi-assets/checkpoints/pi05_libero",
    }
    
    # Map version to config name (used by OpenPI internally for model initialization)
    _config_names = {
        "pi0_base": "pi0_base",
        "pi0_fast_base": "pi0_fast_base",
        "pi05_base": "pi05_base",
        "pi0_fast_droid": "pi0_fast_droid",
        "pi0_droid": "pi0_droid",
        "pi05_droid": "pi05_droid",
        "pi0_aloha_towel": "pi0_aloha_towel",
        "pi0_aloha_tupperware": "pi0_aloha_tupperware",
        "pi0_aloha_pen_uncap": "pi0_aloha_pen_uncap",
        "pi05_libero": "pi05_libero",
    }
    
    # Aliases for convenience
    _gs_checkpoints["latest"] = _gs_checkpoints["pi05_droid"]
    _config_names["latest"] = "pi05_droid"
    
    _container_port: int = 8000
    _startup_timeout: int = 600  # Longer timeout for larger model loading
    _health_check_interval: int = 10

    def info(self) -> Dict:
        """
        Get policy backend information and capabilities.
        
        Returns metadata about the OpenPI policy including supported inputs,
        outputs, available versions, Docker image information, and data source.
        
        :return: Dictionary with policy metadata including name, type, inputs,
                outputs, versions, image, and source (gs for Google Cloud Storage).
        """
        return {
            "name": self.name,
            "type": "policy",
            "inputs": ["image", "state", "prompt"],  # Required inputs for inference
            "outputs": ["action"],  # Model produces action vectors
            "versions": list(self._gs_checkpoints.keys()),  # Available model versions
            "image": self._image,  # Docker image used for serving
            "source": "gs",  # Models stored in Google Cloud Storage
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
        to the OpenPI model and receives a predicted action. The model supports
        multiple observation keys including various camera views and robot state.
        
        OpenPI directly outputs actions in the target action space without
        requiring explicit unnormalization, similar to SmolVLA.
        
        :param handle: Policy handle for the running container.
        :param payload: Observation payload containing image and state keys.
                       Image keys are automatically detected and base64 encoded.
                       Non-image keys (e.g., 'state') are passed through directly.
        :param instruction: Natural language instruction for the task.
        :param model_kwargs: Model-specific parameters (optional for OpenPI).
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
        payload["prompt"] = instruction
        
        try:
            # Send inference request with generous timeout (inference can be slow)
            resp = requests.post(f"{base_url}/act", json=payload, timeout=300)
            resp.raise_for_status()
            
            # Extract action from response
            return resp.json()["action"]
            
        except requests.exceptions.RequestException as e:
            log.error(f"Failed to connect to policy container: {e}")
            raise RuntimeError(f"Failed to get action: {e}")

    def _load_model(
        self,
        handle: PolicyHandle,
        device: str,
        model_load_kwargs: Optional[Dict[str, Any]] = {}
    ) -> None:
        """
        Load OpenPI model into container memory.
        
        Sends a load request to the inference server with the model path,
        device specification, and configuration name. OpenPI requires a
        config_name to identify which model variant to initialize.
        
        :param handle: Policy handle for the running container.
        :param device: Device to load model on ('cuda', 'cuda:0', 'cpu', etc.).
        :param model_load_kwargs: Model loading parameters. If 'config_name' is
                                 not provided, it will be inferred from handle.version.
        :raises ValueError: If config_name cannot be determined for the version.
        :raises RuntimeError: If model loading fails on the server.
        """
        base_url = self._get_base_url(handle)
        
        # Determine config name for model initialization
        config_name = model_load_kwargs.get("config_name")
        if not config_name:
            config_name = self._config_names.get(handle.version)
            if not config_name:
                raise ValueError(f"config_name required for OpenPI version: {handle.version}")
            else:
                model_load_kwargs["config_name"] = config_name
        
        log.info(f"Loading OpenPI model: {config_name} on {device}")
        
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

    def pull(self, version: str, dst: Path) -> Dict:
        """
        Pull model weights and Docker image.
        
        Downloads OpenPI model checkpoints from the public S3 bucket
        or hugging face. Also pulls the Docker image for serving the model.
                
        :param version: Model version to download (e.g., 'pi05_droid', 'pi0_base').
        :param dst: Destination path for model weights (parent directory is used).
        :return: Dictionary with download metadata including name, image, version,
                source, gs_path, config_name, and local path.
        """

        if "gs" in version:
            return self.pull_gs(version, dst)
        else:
            return super().pull(version, dst)

    def pull_gs(self, version: str, dst: Path) -> Dict:
        """
        Pull model weights from Google Cloud Storage and Docker image.
        
        Downloads OpenPI model checkpoints from the public S3 bucket
        gs://openpi-assets using fsspec with anonymous access (no credentials
        required). Also pulls the Docker image for serving the model.
        
        The download uses the same mechanism as the official OpenPI repository,
        with fsspec's gsfs backend for efficient recursive downloads with
        progress tracking.
        
        :param version: Model version to download (e.g., 'pi05_droid', 'pi0_base').
        :param dst: Destination path for model weights (parent directory is used).
        :return: Dictionary with download metadata including name, image, version,
                source, gs_path, config_name, and local path.
        :raises ValueError: If the version is not recognized.
        :raises RuntimeError: If fsspec/gsfs is not installed or download fails.
        """
        # Look up S3 path for requested version
        gs_path = self._gs_checkpoints.get(version)
        if gs_path is None:
            raise ValueError(
                f"Unknown version '{version}' for {self.name}. "
                f"Available: {list(self._gs_checkpoints.keys())}"
            )
        
        # Prepare destination directory
        dst = dst.parent
        dst.mkdir(parents=True, exist_ok=True)
        
        # Pull Docker image first
        self.pull_image()
        
        log.info(f"Downloading {gs_path} to {dst}...")
        
        try:
            import fsspec
            from fsspec.callbacks import TqdmCallback
            
            # Use anonymous access for public bucket (same as openpi repository)
            fs = fsspec.filesystem('gs', anon=True)
            
            # Strip gs:// prefix for fsspec operations
            bucket_path = gs_path.replace('gs://', '')
            
            # Download recursively with progress bar
            fs.get(
                bucket_path,
                str(dst),
                recursive=True,
                callback=TqdmCallback(tqdm_kwargs={"desc": f"Downloading {version}"})
            )
            
            log.info(f"Download complete: {gs_path}")
            
        except ImportError as e:
            raise RuntimeError(
                f"fsspec and gsfs are required for downloading OpenPI models. "
                f"Install with: pip install 'fsspec[gs]' gsfs\n"
                f"Error: {e}"
            )
        except Exception as e:
            raise RuntimeError(f"Failed to download from S3: {e}")
        
        return {
            "name": self.name,
            "image": self._image,
            "version": version,
            "source": "gs",  # Google Cloud Storage
            "gs_path": gs_path,  # Original S3 path
            "config_name": self._config_names.get(version),  # Model config identifier
            "path": str(dst),  # Local download path
        }

    def serve(
        self,
        version: str,
        model_path: Path,
        device: str,
        host_port: Optional[int] = None,
        model_load_kwargs: Optional[Dict[str, Any]] = {}
    ) -> PolicyHandle:
        """
        Start serving OpenPI model in a Docker container.
        
        Launches a container with the OpenPI inference server and loads the
        specified model version. Automatically injects the config_name into
        model_load_kwargs if not already provided, ensuring proper model
        initialization.
        
        :param version: Model version to serve (e.g., 'pi05_droid', 'pi0_base').
        :param model_path: Path to downloaded model weights on host filesystem.
        :param device: Device to load model on ('cuda', 'cuda:0', 'cpu', etc.).
        :param host_port: Optional host port to bind container port to.
                         If None, a random available port is assigned.
        :param model_load_kwargs: Model loading parameters. config_name will be
                                 auto-injected if not provided.
        :return: PolicyHandle for managing the running container and making
                inference requests.
        """
        # Auto-inject config_name if not provided
        if "config_name" not in model_load_kwargs:
            config_name = self._config_names.get(version)
            if config_name:
                model_load_kwargs = {**model_load_kwargs, "config_name": config_name}
        
        # Delegate to parent class serve implementation
        return super().serve(
            version=version,
            model_path=model_path,
            device=device,
            host_port=host_port,
            model_load_kwargs=model_load_kwargs,
        )