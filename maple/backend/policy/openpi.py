"""
OpenPI policy backend.

This module implements the policy backend for OpenPI (π₀ / π₀.₅),
Physical Intelligence's vision-language-action models for robotic manipulation.

OpenPI models are downloaded from the public S3 bucket gs://openpi-assets
using fsspec with anonymous access (no credentials required).
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
    """Backend for OpenPI (π₀ / π₀.₅) vision-language-action models."""
    
    name = "openpi"
    _image = "maplerobotics/openpi:latest"
    
    # Map version strings to S3 checkpoint paths (public bucket, anonymous access)
    _gs_checkpoints = {
        # Base models (for fine-tuning)
        "pi0_base": "gs://openpi-assets/checkpoints/pi0_base",
        "pi0_fast_base": "gs://openpi-assets/checkpoints/pi0_fast_base",
        "pi05_base": "gs://openpi-assets/checkpoints/pi05_base",
        # DROID fine-tuned models
        "pi0_fast_droid": "gs://openpi-assets/checkpoints/pi0_fast_droid",
        "pi0_droid": "gs://openpi-assets/checkpoints/pi0_droid",
        "pi05_droid": "gs://openpi-assets/checkpoints/pi05_droid",
        # ALOHA fine-tuned models
        "pi0_aloha_towel": "gs://openpi-assets/checkpoints/pi0_aloha_towel",
        "pi0_aloha_tupperware": "gs://openpi-assets/checkpoints/pi0_aloha_tupperware",
        "pi0_aloha_pen_uncap": "gs://openpi-assets/checkpoints/pi0_aloha_pen_uncap",
        # LIBERO fine-tuned model
        "pi05_libero": "gs://openpi-assets/checkpoints/pi05_libero",
    }
    
    # Map version to config name (used by openpi internally)
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
    
    # Aliases
    _gs_checkpoints["latest"] = _gs_checkpoints["pi05_droid"]
    _config_names["latest"] = "pi05_droid"
    
    _container_port: int = 8000
    _startup_timeout: int = 600
    _health_check_interval: int = 10

    def info(self) -> Dict:
        return {
            "name": self.name,
            "type": "policy",
            "inputs": ["image", "state", "prompt"],
            "outputs": ["action"],
            "versions": list(self._gs_checkpoints.keys()),
            "image": self._image,
            "source": "gs",
        }

    def act(
        self,
        handle: PolicyHandle,
        payload: Any,
        instruction: str,
        model_kwargs: Optional[Dict[str, Any]] = {},
    ) -> List[float]:
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

    def _load_model(
        self,
        handle: PolicyHandle,
        device: str,
        model_load_kwargs: Optional[Dict[str, Any]] = {}
    ) -> None:
        base_url = self._get_base_url(handle)
        
        config_name = model_load_kwargs.get("config_name")
        if not config_name:
            config_name = self._config_names.get(handle.version)
            if not config_name:
                raise ValueError(f"config_name required for OpenPI")
            else:
                model_load_kwargs["config_name"] = config_name
        
        log.info(f"Loading OpenPI model: {config_name} on {device}")
        
        resp = requests.post(
            f"{base_url}/load",
            json={
                "model_path": "/models/weights",
                "device": device,
                "model_load_kwargs": model_load_kwargs,
            },
            timeout=self._startup_timeout,
        )
        
        if resp.status_code != 200:
            raise RuntimeError(f"Failed to load model: {parse_error_response(resp)}")

    def pull(self, version: str, dst: Path) -> Dict:
        """
        Pull model weights from S3 and Docker image.
        
        Uses fsspec with gsfs and anonymous access (same as openpi repo).
        """
        gs_path = self._gs_checkpoints.get(version)
        if gs_path is None:
            raise ValueError(
                f"Unknown version '{version}' for {self.name}. "
                f"Available: {list(self._gs_checkpoints.keys())}"
            )
        
        dst = dst.parent
        dst.mkdir(parents=True, exist_ok=True)
        self.pull_image()
        
        log.info(f"Downloading {gs_path} to {dst}...")
        
        try:
            import fsspec
            from fsspec.callbacks import TqdmCallback
            
            # Use anonymous access for public bucket (same as openpi)
            fs = fsspec.filesystem('gs', anon=True)
            
            # Strip gs:// prefix for fsspec operations
            bucket_path = gs_path.replace('gs://', '')
            # Download recursively with progress
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
            "source": "gs",
            "gs_path": gs_path,
            "config_name": self._config_names.get(version),
            "path": str(dst),
        }

    def serve(
        self,
        version: str,
        model_path: Path,
        device: str,
        host_port: Optional[int] = None,
        model_load_kwargs: Optional[Dict[str, Any]] = {}
    ) -> PolicyHandle:
        if "config_name" not in model_load_kwargs:
            config_name = self._config_names.get(version)
            if config_name:
                model_load_kwargs = {**model_load_kwargs, "config_name": config_name}
        
        return super().serve(
            version=version,
            model_path=model_path,
            device=device,
            host_port=host_port,
            model_load_kwargs=model_load_kwargs,
        )