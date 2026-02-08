"""
Base environment backend.

This module provides the abstract base class for environment backends in MAPLE.
Environment backends handle the lifecycle of simulation containers, including
pulling images, starting containers, managing health checks, and providing
a unified interface for environment interaction.

Key features:
- Docker-based container management
- Health monitoring and startup validation
- Retry logic for network requests
- Automatic cleanup on failure
- Abstract interface for environment-specific implementations

Environment backends implement task setup, reset, step, and info retrieval
while the base class handles all container orchestration concerns.
"""

import uuid
import time
import requests
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

import docker
from docker.errors import NotFound, APIError

from maple.utils.retry import retry
from maple.utils.logging import get_logger
from maple.utils.config import get_config
from maple.utils.cleanup import register_container, unregister_container

log = get_logger("env.base")

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
    maple_config = get_config()
    try:
        if attr == "memory_limit":
            # Env uses less memory than policy by default
            return maple_config.containers.memory_limit
        elif attr == "startup_timeout":
            return maple_config.containers.startup_timeout
        elif attr == "health_check_interval":
            return maple_config.containers.health_check_interval
    except Exception:
        pass
    return default

@dataclass
class EnvHandle:
    """
    Handle representing a running environment container instance.
    
    Encapsulates all information needed to interact with a running
    environment container, including connection details and metadata.
    """
    env_id: str
    backend_name: str
    device: str
    host: str
    port: str
    container_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        """
        Convert handle to dictionary representation.

        :return: Dictionary containing all handle fields.
        """
        return {
            "env_id": self.env_id,
            "device": self.device,
            "backend_name": self.backend_name,
            "host": self.host,
            "port": self.port,
            "container_id": self.container_id,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, d: dict) -> "EnvHandle":
        """
        Create handle from dictionary representation.
        
        :param d: Dictionary containing handle fields.
        :return: EnvHandle instance reconstructed from dictionary.
        """
        return cls(**d)

class EnvBackend(ABC):
    """
    Abstract base class for environment backends.
    
    Provides Docker container management, health monitoring, and a unified
    interface for environment operations. Subclasses must implement
    environment-specific task listing and can override container configuration.
    
    The backend handles:
    - Container lifecycle (start, stop, health checks)
    - Network communication with retry logic
    - Port mapping and startup validation
    - Cleanup on failure
    """
    
    name: str
    _image: str
    _container_port: int = 8000
    _startup_timeout: int = 120
    _health_check_interval: int = 2
    _memory_limit: str = "4g"

    def __init__(self):
        """
        Initialize the environment backend.
        
        Sets up Docker client connection and initializes container tracking.
        Loads configuration values with fallback to class defaults.
        """
        # Initialize Docker client from environment
        self.client = docker.from_env()
        
        # Track active environment handles
        self._active_handles: Dict[str, EnvHandle] = {}

        # Load configuration with defaults
        self._startup_timeout = _get_config_value("startup_timeout", self._startup_timeout)
        self._health_check_interval = _get_config_value("health_check_interval", self._health_check_interval)

    def _get_base_url(self, handle: EnvHandle) -> str:
        """
        Get base URL for HTTP requests to container.
        
        :param handle: Environment handle with host and port information.
        :return: Base URL string for making requests.
        """
        return f"http://{handle.host}:{handle.port}"

    def _wait_for_ready(self, handle: EnvHandle) -> bool:
        """
        Wait for container to be ready to accept requests.
        
        Polls the container's health endpoint until it responds successfully
        or the startup timeout is reached. Uses exponential backoff for
        efficient polling.
        
        :param handle: Environment handle to check.
        :return: True if container became ready, False if timeout reached.
        """
        base_url = self._get_base_url(handle)
        deadline = time.time() + self._startup_timeout

        log.debug(f"Waiting for container {handle.env_id} to be ready....")
        
        while time.time() < deadline:
            try:
                # Attempt health check
                resp = requests.get(f"{base_url}/health", timeout=5)
                if resp.status_code == 200:
                    log.debug(f"Container {handle.env_id} is ready")
                    return True
            except requests.exceptions.ConnectionError:
                # Container not yet accepting connections
                pass
            except requests.exceptions.Timeout:
                # Container responding but slow
                pass
            
            # Wait before next poll
            time.sleep(self._health_check_interval)
        
        log.error(f"Container {handle.env_id} failed to become ready within {self._startup_timeout}s")
        return False
    
    def health(self, handle: EnvHandle) -> Dict:
        """
        Check health of a specific environment instance.
        
        Performs a health check by querying the container's health endpoint.
        Used by the daemon's health monitor to detect container failures.
        
        :param handle: Environment handle to check.
        :return: Health status dictionary with 'status' field.
        """
        base_url = self._get_base_url(handle)
        
        try:
            resp = requests.get(f"{base_url}/health", timeout=5)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.RequestException as e:
            log.warning(f"Health check failed for {handle.env_id}: {e}")
            return {"status": "error", "error": str(e)}

    def pull(self) -> Dict:
        """
        Pull or verify the environment Docker image.
        
        Attempts to pull the image from a registry. If pull fails, checks
        if the image exists locally. If neither succeeds, raises an error
        with build instructions.
        
        :return: Dictionary with image information and source (pulled/local).
        """
        # Try to pull from registry
        try:
            log.info(f"Pulling Docker image {self._image}...")
            image = self.client.images.pull(self._image)
            log.info(f"Image pulled: {self._image}")
            return {
                "env": self.name,
                "image": self._image,
                "source": "pulled",
            }
        except APIError:
            # Pull failed, check local
            pass
        
        # Check if image exists locally
        try:
            image = self.client.images.get(self._image)
            log.debug(f"Image found locally: {self._image}")
            return {
                "env": self.name,
                "image": self._image,
                "source": "local",
            }
        except NotFound:
            # Image not available
            raise RuntimeError(
                f"Image {self._image} not found. "
                f"Build it with: docker build -t {self._image} docker/libero/"
            )
    
    def serve(self, num_envs: int = 1, device: str= "cpu", host_port: Optional[int] = None) -> List[EnvHandle]:
        """
        Start environment container(s).
        
        Launches one or more Docker containers for parallel environment
        execution. Each container gets a unique ID and is registered for
        cleanup tracking. Validates startup by waiting for health checks.
        
        :param num_envs: Number of environment containers to start.
        :param host_port: Optional specific port to bind (only valid with num_envs=1).
        :return: List of EnvHandle instances for the started containers.
        """
        handles = []
        
        # Validate host_port usage
        if host_port is not None and num_envs > 1:
            raise ValueError("host_port can only be specified when num_envs=1")
        
        log.info(f"Starting {num_envs} {self.name} environment(s)...")
        log.debug(f"  Device: {device}")

        for i in range(num_envs):
            # Generate unique environment ID
            env_id = f"{self.name}-{uuid.uuid4().hex[:8]}"
            
            # Configure port mapping
            if host_port is not None:
                port_mapping = {f"{self._container_port}/tcp": host_port}
            else:
                # Let Docker assign random port
                port_mapping = {f"{self._container_port}/tcp": None}
            
            container = None
            try:
                # Get environment-specific container configuration
                config = self._get_container_config(device)
                
                # Start container with configured settings
                container = self.client.containers.run(
                    self._image,
                    detach=True,  # Run in background
                    remove=True,  # Auto-remove on stop
                    name=env_id,
                    ports=port_mapping,
                    labels={
                        "vla.env": self.name,
                        "vla.env_id": env_id,
                    },
                    mem_limit=self._memory_limit,
                    environment=config.get("environment", {}),
                    volumes=config.get("volumes", {}),
                    device_requests=config.get("device_requests", []),
                )
                
                # Register for cleanup tracking
                register_container(container.id, env_id)
                log.debug(f"Container started: {env_id} ({container.id[:12]})")
                
                # Wait for port mapping to be assigned
                actual_port = self._wait_for_port(container)
                if actual_port is None:
                    raise RuntimeError(f"Could not get port mapping for container {env_id}")
                
                log.debug(f"Container port mapped: {env_id} -> {actual_port}")
                
                # Create handle for this environment
                handle = EnvHandle(
                    env_id=env_id,
                    device=device,
                    backend_name=self.name,
                    host="127.0.0.1",
                    port=actual_port,
                    container_id=container.id,
                    metadata={"status": "starting"},
                )
                
                # Wait for container to become healthy
                if self._wait_for_ready(handle):
                    handle.metadata["status"] = "ready"
                else:
                    raise RuntimeError(f"Container {env_id} failed to start within {self._startup_timeout}s")
                
                # Track handle and add to return list
                self._active_handles[env_id] = handle
                handles.append(handle)
                
                log.info(f"Environment {env_id} ready on port {actual_port}")
                
            except Exception as e:
                # Cleanup on failure
                if container:
                    log.warning(f"Cleaning up failed container {env_id}")
                    try:
                        container.stop(timeout=5)
                    except Exception:
                        pass
                    unregister_container(container.id)
                
                # Stop all previously started containers
                for h in handles:
                    self._stop_single(h)
                raise RuntimeError(f"Failed to start env {i+1}/{num_envs}: {e}")
        
        return handles

    def _wait_for_port(self, container, max_attempts: int = 10) -> Optional[int]:
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
    
    def _stop_single(self, handle: EnvHandle) -> None:
        """
        Stop a single environment container.
        
        Stops the Docker container and unregisters it from cleanup tracking.
        Safe to call even if container is already stopped.
        
        :param handle: Environment handle to stop.
        """
        log.debug(f"Stopping env: {handle.env_id}")
        
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
        self._active_handles.pop(handle.env_id, None)
    
    def stop(self, handles: List[EnvHandle]) -> None:
        """
        Stop multiple environment containers.
        
        Stops all provided environment containers and cleans up resources.
        
        :param handles: List of environment handles to stop.
        """
        for handle in handles:
            self._stop_single(handle)

    @retry(max_attempts=2, delay=0.5, exceptions=(requests.exceptions.ConnectionError,))
    def _post(self, url: str, json: dict = None, params: dict = None, timeout: int = 30) -> requests.Response:
        """
        POST request with automatic retry logic.
        
        Makes a POST request with retry on connection failures. Used for
        all environment container communication to handle transient issues.
        
        :param url: Full URL to POST to.
        :param json: Optional JSON body.
        :param params: Optional query parameters.
        :param timeout: Request timeout in seconds.
        :return: Response object from successful request.
        """
        return requests.post(url, json=json, params=params, timeout=timeout)
    
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
            raise RuntimeError(f"Env container error ({resp.status_code}): {detail}")
        return resp.json()
        
    def setup(self, handle: EnvHandle, task: str, seed: Optional[int] = None, env_kwargs: Optional[Dict[str, Any]] = {}) -> Dict:
        """
        Setup environment with a specific task.
        
        Configures the environment to run a particular task, loading
        necessary assets and returning task metadata like instructions.
        Updates handle metadata with task information.
        
        :param handle: Environment handle to setup.
        :param task: Task specification string.
        :param seed: Optional random seed for task setup.
        :param env_kwargs: Model-specific parameters.
        :return: Task metadata including instruction and task details.
        """
        base_url = self._get_base_url(handle)
        log.info(f"Setting up env {handle.env_id} with task: {task}")
        
        # Build request payload
        payload = {"task": task, "env_kwargs": env_kwargs}
        if seed is not None:
            payload["seed"] = seed
        
        try:
            # Send setup request with longer timeout (task loading can be slow)
            resp = self._post(f"{base_url}/setup", json=payload, timeout=60)
            result = self._handle_response(resp, "setup")
            
            # Update handle metadata
            handle.metadata["task"] = result.get("task")
            handle.metadata["instruction"] = result.get("instruction")
            handle.metadata["env_kwargs"] = result.get("env_kwargs")
            handle.metadata["status"] = "setup"
            
            log.debug(f"Env {handle.env_id} setup complete: {result.get('task')}")
            return result
            
        except requests.exceptions.RequestException as e:
            log.error(f"Failed to setup env {handle.env_id}: {e}")
            raise RuntimeError(f"Failed to setup env {handle.env_id}: {e}")
    
    def reset(self, handle: EnvHandle, seed: Optional[int] = None) -> Dict:
        """
        Reset the environment to initial state.
        
        Resets the environment for the current task and returns the
        initial observation.
        
        :param handle: Environment handle to reset.
        :param seed: Optional random seed for reset.
        :return: Dictionary containing initial observation.
        """
        base_url = self._get_base_url(handle)
        log.debug(f"Resetting env {handle.env_id}")
        
        # Build query parameters
        params = {}
        if seed is not None:
            params["seed"] = seed
        
        try:
            resp = self._post(f"{base_url}/reset", params=params, timeout=30)
            return self._handle_response(resp, "reset")
        except requests.exceptions.RequestException as e:
            log.error(f"Failed to reset env {handle.env_id}: {e}")
            raise RuntimeError(f"Failed to reset env {handle.env_id}: {e}")
    
    def step(self, handle: EnvHandle, action: List[float]) -> Dict:
        """
        Take a step in the environment with an action.
        
        Executes the provided action and returns the resulting observation,
        reward, and termination flags.
        
        :param handle: Environment handle to step.
        :param action: Action vector to execute.
        :return: Dictionary with observation, reward, terminated, truncated.
        """
        base_url = self._get_base_url(handle)
        
        try:
            resp = requests.post(f"{base_url}/step", json={"action": action}, timeout=30)
            return self._handle_response(resp, "step")
        except requests.exceptions.RequestException as e:
            log.error(f"Failed to step env {handle.env_id}: {e}")
            raise RuntimeError(f"Failed to step env {handle.env_id}: {e}")
    
    def get_info(self, handle: EnvHandle) -> Dict:
        """
        Get environment information and metadata.
        
        Returns information about the environment including current task,
        action space, observation space, and other metadata.
        
        :param handle: Environment handle to query.
        :return: Dictionary with environment metadata.
        """
        base_url = self._get_base_url(handle)
        
        try:
            resp = requests.get(f"{base_url}/info", timeout=10)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.RequestException as e:
            log.error(f"Failed to get info for env {handle.env_id}: {e}")
            raise RuntimeError(f"Failed to get info for env {handle.env_id}: {e}")
        
    @abstractmethod
    def list_tasks(self, suite: Optional[str] = None) -> Dict:
        """
        List available tasks for this environment.
        
        Must be implemented by subclasses to provide environment-specific
        task enumeration. Returns tasks organized by suite name.
        
        :param suite: Optional suite name to filter results.
        :return: Dictionary mapping suite names to task lists. Each task
                should include fields like 'index', 'name', 'instruction'.
        """
        pass
    
    def _get_container_config(self, device: str) -> Dict:
        """
        Get container configuration for Docker.
        
        Override in subclass to provide custom container configuration.
        The base implementation handles GPU device requests and environment
        variables for CUDA and attention configuration.
        
        :param device: Device string ('cpu', 'cuda:0', etc.).
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
            },
            "device_requests": device_requests,
        }