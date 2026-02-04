"""
Base class for policy backends.

This module provides the abstract base class for policy backends that manage
vision-language-action models. Policy backends handle the complete lifecycle
of policy containers including:

- Pulling model weights from HuggingFace
- Managing Docker containers with GPU support
- Loading models with various configurations
- Serving inference requests via HTTP API
- Health monitoring and cleanup

Key features:
- Docker-based containerization for isolation
- GPU device management and CUDA configuration
- Automatic port mapping and health checks
- Image encoding utilities for observations
- Retry logic for network requests
- Configuration management with defaults
"""

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
from docker.client.containers import Container
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from huggingface_hub import snapshot_download

from maple.utils.retry import retry
from maple.utils.logging import get_logger
from maple.config import config as maple_config
from maple.utils.cleanup import register_container, unregister_container

log = get_logger("policy.base")

def _get_config_value(attr: str, default: Any) -> Any:
    """
    Get configuration value with fallback to default.
    
    Attempts to retrieve a configuration value from the MAPLE config.
    If the config is not loaded or the attribute doesn't exist, returns
    the provided default value.
    
    :param attr: Configuration attribute name to retrieve.
    :param default: Default value to use if config unavailable.
    :return: Configuration value or default.
    """
    try:
        if attr == "memory_limit":
            return maple_config.containers.memory_limit
        elif attr == "shm_size":
            return maple_config.containers.shm_size
        elif attr == "startup_timeout":
            return maple_config.containers.startup_timeout
        elif attr == "health_check_interval":
            return maple_config.containers.health_check_interval
    except Exception:
        pass
    return default

@dataclass
class PolicyHandle:
    """
    Handle representing a running policy container instance.
    
    Encapsulates all information needed to interact with a running
    policy container, including connection details, model metadata,
    and container configuration.
    """
    
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
        """
        Convert handle to dictionary representation.
        
        :return: Dictionary containing all handle fields.
        """
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
        """
        Create handle from dictionary representation.
        
        :param d: Dictionary containing handle fields.
        :return: PolicyHandle instance reconstructed from dictionary.
        """
        return cls(**d)


class PolicyBackend(ABC):
    """
    Abstract base class for Docker-based policy backends.
    
    Provides comprehensive container management and model serving capabilities
    for vision-language-action policies. Handles Docker orchestration, GPU
    configuration, health monitoring, and HTTP-based inference.
    
    The backend manages the full lifecycle:
    1. Pull: Download Docker image and model weights from HuggingFace
    2. Serve: Start container with GPU support and load model
    3. Act: Serve inference requests with image encoding
    4. Stop: Clean up container and resources
    
    Configuration is read from ~/.vla/config.yaml with fallback to class defaults.
    """
    
    name: str
    _image: str
    _hf_repos: Dict[str, str]  # version -> HuggingFace repo ID
    _container_port: int = 8000
    _startup_timeout: int = 300
    _health_check_interval: int = 5
    _memory_limit: str = "32g"
    _shm_size: str = "2g"

    def __init__(self):
        """
        Initialize the policy backend.
        
        Sets up Docker client connection and initializes container tracking.
        Loads configuration values with fallback to class defaults.
        """
        # Initialize Docker client from environment
        self.client = docker.from_env()
        
        # Track active policy handles
        self._active_handles: Dict[str, PolicyHandle] = {}

        # Load configuration with defaults
        self._memory_limit = _get_config_value("memory_limit", self._memory_limit)
        self._shm_size = _get_config_value("shm_size", self._shm_size)
        self._startup_timeout = _get_config_value("startup_timeout", self._startup_timeout)
        self._health_check_interval = _get_config_value("health_check_interval", self._health_check_interval)

    @abstractmethod
    def info(self) -> Dict:
        """
        Get backend information and capabilities.
        
        Must be implemented by subclasses to provide backend-specific
        metadata including supported inputs, outputs, and versions.
        
        :return: Dictionary with backend metadata (name, type, inputs, outputs, versions).
        """
        pass

    @abstractmethod
    def act(
        self, 
        handle: PolicyHandle, 
        payload: Any, 
        instruction: str, 
        unnorm_key: Optional[str] = None
    ) -> List[float]:
        """
        Get action prediction from the policy.
        
        Must be implemented by subclasses to provide inference logic.
        Takes transformed observations and returns predicted actions.
        
        :param handle: Policy handle for the running container.
        :param payload: Transformed observation from environment (post-adapter).
        :param instruction: Natural language instruction for the task.
        :param unnorm_key: Optional dataset key for action unnormalization.
        :return: Predicted action as list of floats.
        """
        pass

    def _get_base_url(self, handle: PolicyHandle) -> str:
        """
        Get base URL for HTTP requests to container.
        
        :param handle: Policy handle with host and port information.
        :return: Base URL string for making requests.
        """
        return f"http://{handle.host}:{handle.port}"

    def wait_for_ready(self, handle: PolicyHandle) -> bool:
        """
        Wait for container to be ready to accept requests.
        
        Polls the container's health endpoint until it responds successfully
        or the startup timeout is reached. Used during container initialization
        to ensure the server is running before attempting to load the model.
        
        :param handle: Policy handle to check.
        :return: True if container became ready, False if timeout reached.
        """
        base_url = self._get_base_url(handle)
        deadline = time.time() + self._startup_timeout

        log.debug(f"Waiting for container {handle.policy_id} to be ready...")
        
        while time.time() < deadline:
            try:
                # Attempt health check
                resp = requests.get(f"{base_url}/health", timeout=5)
                if resp.status_code == 200:
                    log.debug(f"Container {handle.policy_id} is ready")
                    return True
            except requests.exceptions.ConnectionError:
                # Container not yet accepting connections
                pass
            except requests.exceptions.Timeout:
                # Container responding but slow
                pass
            
            # Wait before next poll
            time.sleep(self._health_check_interval)
        
        log.error(f"Container {handle.policy_id} failed to become ready within {self._startup_timeout}s")
        return False

    def _encode_image(self, image: Any) -> str:
        """
        Encode image to base64 string for HTTP transmission.
        
        Handles multiple image formats and converts them to PNG-encoded
        base64 strings for transmission to the policy container.
        
        :param image: Image to encode (PIL Image, numpy array, or base64 string).
        :return: Base64-encoded PNG image string.
        """
        # If already base64 encoded, return as-is
        if isinstance(image, str):
            return image
        
        # Convert numpy array to PIL Image
        if isinstance(image, np.ndarray):
            # Ensure uint8 format
            if image.dtype != np.uint8:
                image = (image * 255).astype(np.uint8)
            image = Image.fromarray(image)
        elif isinstance(image, Image.Image):
            # Already PIL Image
            image = image
        else:
            raise ValueError(f"Unsupported image type: {type(image)}")
        
        # Encode as PNG and convert to base64
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return base64.b64encode(buffer.getvalue()).decode("utf-8")

    def serve(
        self,
        version: str,
        model_path: Path,
        device: str,
        host_port: Optional[int] = None,
        attn_implementation: str = "sdpa"
    ) -> PolicyHandle:
        """
        Start policy container and load model.
        
        Orchestrates the complete container startup and model loading process:
        1. Start Docker container with GPU support
        2. Wait for container to become healthy
        3. Load model weights with specified configuration
        4. Verify model is ready for inference
        
        The container is configured with:
        - Model weights mounted as read-only volume
        - GPU device request if CUDA device specified
        - Memory and shared memory limits
        - Port mapping for HTTP API
        
        :param version: Model version to serve (must exist in _hf_repos).
        :param model_path: Filesystem path to model weights.
        :param device: Device to load model on ('cpu', 'cuda:0', etc.).
        :param host_port: Optional specific port to bind (random if None).
        :param attn_implementation: Attention mechanism ('sdpa', 'flash_attention_2', 'eager').
        :return: PolicyHandle for the running container.
        """
        # Generate unique policy ID
        policy_id = f"{self.name}-{version}-{uuid.uuid4().hex[:8]}"
        
        log.info(f"Starting policy container: {policy_id}")
        log.debug(f"  Model path: {model_path}")
        log.debug(f"  Device: {device}")
        log.debug(f"  Attention: {attn_implementation}")
        
        # Configure port mapping
        if host_port is not None:
            port_mapping = {f"{self._container_port}/tcp": host_port}
        else:
            # Let Docker assign random port
            port_mapping = {f"{self._container_port}/tcp": None}
        
        # Get device-specific container configuration
        config = self._get_container_config(device, attn_implementation)
        
        container = None
        try:
            # Start container with configured settings
            container = self.client.containers.run(
                self._image,
                detach=True,  # Run in background
                remove=True,  # Auto-remove on stop
                name=policy_id,
                ports=port_mapping,
                volumes={
                    # Mount model weights as read-only
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
                mem_limit=self._memory_limit,
                shm_size=self._shm_size,  # Important for PyTorch dataloaders
            )
            
            # Register for cleanup tracking
            register_container(container.id, policy_id)
            log.debug(f"Container started: {container.id[:12]}")
            
            # Wait for port mapping to be assigned
            actual_port = self._wait_for_port(container)
            if actual_port is None:
                raise RuntimeError(f"Could not get port mapping for container {policy_id}")
            
            log.debug(f"Container port mapped: {actual_port}")
            
            # Create handle for this policy
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
            
            # Wait for container to become healthy
            if not self._wait_for_ready(handle):
                raise RuntimeError(f"Container {policy_id} failed to start within {self._startup_timeout}s")
            
            # Load model into container
            self._load_model(handle, device, attn_implementation)
            
            # Mark as ready
            handle.metadata["status"] = "ready"
            self._active_handles[policy_id] = handle
            
            log.info(f"Policy {policy_id} ready on port {actual_port}")
            return handle
            
        except Exception as e:
            # Cleanup on failure
            if container:
                log.warning(f"Cleaning up failed container {policy_id}")
                try:
                    container.stop(timeout=5)
                except Exception:
                    pass
                unregister_container(container.id)
            
            raise RuntimeError(f"Failed to serve policy: {e}")

    def _wait_for_port(self, container: Container, max_attempts: int = 10) -> Optional[int]:
        """
        Wait for container port mapping to be available.
        
        Docker may take a moment to assign the host port mapping. This
        polls the container attributes until the mapping is available.
        
        :param container: Docker container object.
        :param max_attempts: Maximum number of polling attempts.
        :return: Host port number if found, None if timeout.
        """
        for _ in range(max_attempts):
            # Reload container attributes from Docker
            container.reload()
            port_info = container.attrs["NetworkSettings"]["Ports"]
            port_key = f"{self._container_port}/tcp"
            
            # Check if port mapping exists
            if port_info and port_key in port_info and port_info[port_key]:
                return int(port_info[port_key][0]["HostPort"])
            
            # Wait before next attempt
            time.sleep(0.5)
        return None

    def _load_model(self, handle: PolicyHandle, device: str, attn_implementation: str) -> None:
        """
        Load model inside the running container.
        
        Sends a request to the container's /load endpoint to load the model
        weights with the specified device and attention configuration. This
        can take several minutes for large models.
        
        :param handle: Policy handle for the container.
        :param device: Device to load model on.
        :param attn_implementation: Attention implementation to use.
        """
        base_url = self._get_base_url(handle)
        
        log.info(f"Loading model on {device} with {attn_implementation} attention...")
        
        # Send load request with generous timeout (model loading is slow)
        resp = requests.post(
            f"{base_url}/load",
            json={
                "model_path": "/models/weights",
                "device": device,
                "attn_implementation": attn_implementation,
            },
            timeout=self._startup_timeout,
        )
        
        # Check for errors
        if resp.status_code != 200:
            error_detail = resp.json().get('detail', resp.text) if resp.text else "Unknown error"
            raise RuntimeError(f"Failed to load model: {error_detail}")

    def stop(self, handle: PolicyHandle) -> None:
        """
        Stop a running policy container.
        
        Stops the Docker container and unregisters it from cleanup tracking.
        Safe to call even if container is already stopped.
        
        :param handle: Policy handle to stop.
        """
        log.info(f"Stopping policy: {handle.policy_id}")
        
        if handle.container_id:
            try:
                # Get container and stop it
                container = self.client.containers.get(handle.container_id)
                container.stop(timeout=10)
                log.debug(f"Container stopped: {handle.container_id[:12]}")
            except NotFound:
                # Container already removed (auto-remove on stop)
                log.debug(f"Container already removed: {handle.container_id[:12]}")
            
            # Unregister from cleanup tracking
            unregister_container(handle.container_id)
        
        # Remove from active handles
        self._active_handles.pop(handle.policy_id, None)

    def get_info(self, handle: PolicyHandle) -> Dict:
        """
        Get information about a running policy instance.
        
        Queries the container for metadata about the loaded model including
        input/output specifications and version information.
        
        :param handle: Policy handle to query.   
        :return: Dictionary with policy metadata.

        """
        base_url = self._get_base_url(handle)
        
        try:
            resp = requests.get(f"{base_url}/info", timeout=10)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.RequestException as e:
            log.error(f"Failed to get policy info: {e}")
            raise RuntimeError(f"Failed to get policy info: {e}")

    def pull_image(self) -> Dict:
        """
        Pull or verify the policy Docker image.
        
        Attempts to pull the image from a registry. If pull fails, checks
        if the image exists locally. If neither succeeds, raises an error
        with build instructions.
        
        :return: Dictionary with image information and source (pulled/local).
        """
        # Try to pull from registry
        try:
            log.info(f"Pulling Docker image {self._image}...")
            self.client.images.pull(self._image)
            log.info(f"Image pulled: {self._image}")
            return {"image": self._image, "source": "pulled"}
        except APIError:
            # Pull failed, check local
            pass
        
        # Check if image exists locally
        try:
            self.client.images.get(self._image)
            log.debug(f"Image found locally: {self._image}")
            return {"image": self._image, "source": "local"}
        except NotFound:
            # Image not available
            raise RuntimeError(
                f"Image {self._image} not found. "
                f"Build it with: docker build -t {self._image} docker/{self.name}/"
            )

    def pull(self, version: str, dst: Path) -> Dict:
        """
        Pull model weights from HuggingFace and Docker image.
        
        Downloads the specified model version from HuggingFace Hub and
        ensures the Docker image is available locally. This prepares
        everything needed to serve the policy.
        
        :param version: Model version to pull (must exist in _hf_repos).
        :param dst: Destination directory for model weights.
        :return: Dictionary with pull metadata (name, version, repo, path).
        """
        # Validate version
        repo = self._hf_repos.get(version)
        if repo is None:
            raise ValueError(f"Unknown version '{version}' for {self.name}")
        
        # Create destination directory
        dst.mkdir(parents=True, exist_ok=True)
        
        # Pull Docker image
        self.pull_image()
        
        # Download model weights from HuggingFace
        log.info(f"Downloading {repo} to {dst}...")
        snapshot_download(
            repo_id=repo,
            local_dir=dst,
        )
        log.info(f"Download complete: {repo}")
        
        return {
            "name": self.name,
            "version": version,
            "source": "huggingface",
            "repo": repo,
            "path": str(dst),
        }

    def health(self, handle: PolicyHandle) -> Dict:
        """
        Check health of a policy instance.
        
        Performs a health check by querying the container's health endpoint.
        Used by the daemon's health monitor to detect container failures.
        
        :param handle: Policy handle to check.
        :return: Health status dictionary with 'status' field.
        """
        base_url = self._get_base_url(handle)
        
        try:
            resp = requests.get(f"{base_url}/health", timeout=5)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.RequestException as e:
            log.warning(f"Health check failed for {handle.policy_id}: {e}")
            return {"status": "error", "error": str(e)}

    def _get_container_config(self, device: str, attn_implementation: str) -> Dict:
        """
        Get container configuration for Docker.
        
        Override in subclass to provide custom container configuration.
        The base implementation handles GPU device requests and environment
        variables for CUDA and attention configuration.
        
        :param device: Device string ('cpu', 'cuda:0', etc.).
        :param attn_implementation: Attention implementation string.
        :return: Dictionary with environment, device_requests.
        """
        # Parse GPU index from device string
        gpu_idx = "0"
        device_requests = []
        
        if device.startswith("cuda"):
            # Extract GPU index (e.g., "cuda:1" -> "1")
            gpu_idx = device.split(":")[-1] if ":" in device else "0"
            
            # Create GPU device request for Docker
            device_requests = [
                docker.types.DeviceRequest(
                    device_ids=[gpu_idx],
                    capabilities=[["gpu"]]
                )
            ]
        
        return {
            "environment": {
                # Set CUDA_VISIBLE_DEVICES to restrict GPU visibility
                "CUDA_VISIBLE_DEVICES": gpu_idx if device.startswith("cuda") else "",
                "ATTN_IMPLEMENTATION": attn_implementation,
            },
            "device_requests": device_requests,
        }

    @retry(max_attempts=3, delay=0.5, exceptions=(requests.exceptions.ConnectionError, requests.exceptions.Timeout))
    def _post_with_retry(self, url: str, json: dict, timeout: int) -> requests.Response:
        """
        POST request with automatic retry logic.
        
        Makes a POST request with retry on connection failures and timeouts.
        Used for policy container communication to handle transient issues.
        
        :param url: Full URL to POST to.
        :param json: JSON body for the request.
        :param timeout: Request timeout in seconds.
        :return: Response object from successful request.
        """
        return requests.post(url, json=json, timeout=timeout)

    def _handle_response(self, resp: requests.Response, operation: str) -> Dict:
        """
        Handle HTTP response and extract JSON, raising on errors.
        
        Checks response status and extracts JSON body. On error, attempts
        to extract error detail from response for better error messages.
        
        :param resp: Response object to handle.
        :param operation: Operation name for error messages.
        :return: JSON response body.

        """
        if resp.status_code != 200:
            # Try to extract error detail
            try:
                detail = resp.json().get("detail", resp.text)
            except Exception:
                detail = resp.text
            log.error(f"Policy container error: {detail}")
            raise RuntimeError(f"Policy container error ({resp.status_code}): {detail}")
        return resp.json()

    def _wait_for_ready(self, handle: PolicyHandle) -> bool:
        """
        Wait for container to be ready to accept requests.
        
        Polls the container's health endpoint until it responds successfully
        or the startup timeout is reached. This is the primary readiness check
        used during container initialization.
        
        :param handle: Policy handle to check.
        :return: True if container became ready, False if timeout reached.
        """
        base_url = self._get_base_url(handle)
        deadline = time.time() + self._startup_timeout

        log.debug(f"Waiting for container {handle.policy_id} to be ready...")
        
        while time.time() < deadline:
            try:
                # Attempt health check with longer timeout
                resp = requests.get(f"{base_url}/health", timeout=10)
                if resp.status_code == 200:
                    log.debug(f"Container {handle.policy_id} is ready")
                    return True
            except requests.exceptions.ConnectionError:
                # Container not yet accepting connections
                pass
            except requests.exceptions.Timeout:
                # Container responding but slow
                pass
            
            # Wait before next poll
            time.sleep(self._health_check_interval)
        
        log.error(f"Container {handle.policy_id} failed to become ready within {self._startup_timeout}s")
        return False