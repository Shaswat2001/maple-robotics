"""
LIBERO environment backend.

This module implements the environment backend for LIBERO (Language-Instructed
Benchmarks for Embodied Robot Learning), a suite of robotic manipulation tasks
with natural language instructions.

LIBERO provides multiple task suites:
- libero_spatial: 10 spatial reasoning tasks
- libero_object: 10 object manipulation tasks
- libero_goal: 10 goal-conditioned tasks
- libero_10: 10 diverse benchmark tasks
- libero_90: 90 diverse tasks for large-scale evaluation

The backend handles Docker container management and provides task enumeration
both statically (when no container is running) and dynamically (by querying
a running container for detailed task information).
"""

import requests
from typing import Optional

from maple.backend.envs.base import EnvBackend
from maple.utils.logging import get_logger

log = get_logger("env.libero")

class LiberoEnvBackend(EnvBackend):
    """
    Backend for LIBERO manipulation environments.
    
    Manages LIBERO environment containers with MuJoCo physics simulation
    using OSMesa for headless rendering. Provides access to multiple task
    suites with language-conditioned manipulation tasks.
    
    The backend uses the maplerobotics/libero:latest Docker image which
    includes LIBERO, MuJoCo, and all necessary dependencies pre-configured.
    """
    
    name = "libero"
    _image = "maplerobotics/libero:latest"
    _container_port: int = 8000
    _startup_timeout: int = 120
    _health_check_interval: int = 2
    _memory_limit: str = "4g"

    def _get_container_config(self, device: str) -> dict:
        """
        Get LIBERO-specific container configuration.
        
        Configures the container with:
        - MUJOCO_GL=osmesa: Use OSMesa for headless rendering (no GPU required)
        - No volume mounts: All assets included in image
        - No device requests: CPU-only rendering
        
        :param device: Device string ('cpu', 'cuda:0', etc.).
        :return: Dictionary with environment variables, volumes, and device requests.
        """
        config = super()._get_container_config(device)
        config["environment"]["MUJOCO_GL"] = "osmesa"
        return config

    def list_tasks(self, suite: Optional[str] = None) -> dict:
        """
        List available LIBERO tasks.
        
        Returns task information in two modes:
        1. Dynamic mode (if container running): Queries container for detailed
           task list including task names, indices, and instructions.
        2. Static mode (no container): Returns suite descriptions with counts.
        
        The dynamic mode provides complete task details by querying a running
        container's /tasks endpoint, which returns the full task registry.
        
        :param suite: Optional suite name to filter results (e.g., 'libero_10').
        
        :return: Dictionary mapping suite names to task information. In dynamic
                mode, each suite maps to a list of task dicts with 'index',
                'name', and 'instruction'. In static mode, suites map to
                description dicts with 'description' and 'count'.
        """
        # If we have an active container, use it for dynamic task listing
        if self._active_handles:
            # Get any active handle to query
            handle = next(iter(self._active_handles.values()))
            base_url = self._get_base_url(handle)
            
            try:
                # Build query parameters
                params = {}
                if suite:
                    params["suite"] = suite
                
                # Query container for task list
                resp = requests.get(f"{base_url}/tasks", params=params, timeout=30)
                resp.raise_for_status()
                return resp.json()
                
            except requests.exceptions.RequestException:
                # Container query failed, fall back to static info
                pass
        
        # Fallback: return static task suite information
        # This is returned when no container is running or query fails
        return {
            "libero_spatial": {
                "description": "10 spatial reasoning tasks",
                "count": 10
            },
            "libero_object": {
                "description": "10 object manipulation tasks",
                "count": 10
            },
            "libero_goal": {
                "description": "10 goal-conditioned tasks",
                "count": 10
            },
            "libero_10": {
                "description": "10 diverse tasks",
                "count": 10
            },
            "libero_90": {
                "description": "90 diverse tasks",
                "count": 90
            },
            "_note": "Start an env to get full task listings with instructions",
        }