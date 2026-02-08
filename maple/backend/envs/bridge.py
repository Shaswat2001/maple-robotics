"""
Bridge environment backend.

This module implements the environment backend for Bridge Dataset, 
a suite of robotic manipulation tasks with natural language instructions.

Bridge provides multiple task suites:
- bridge: 4 task with the WidowX robot

The backend handles Docker container management and provides task enumeration
both statically (when no container is running) and dynamically (by querying
a running container for detailed task information).
"""

import requests
from typing import Optional

from maple.backend.envs.base import EnvBackend
from maple.utils.logging import get_logger

log = get_logger("env.bridge")

class BridgeBackend(EnvBackend):
    """
    Backend for Bridge manipulation environments.
    
    Manages Bridge environment containers with MuJoCo physics simulation
    using EGL for headless rendering. Provides access to multiple task
    suites with language-conditioned manipulation tasks.
    
    The backend uses the maplerobotics/simplerenv:latest Docker image which
    includes Bridge, and all necessary dependencies pre-configured.
    """
    
    name = "bridge"
    _image = "maplerobotics/simplerenv:latest"
    _container_port: int = 8000
    _startup_timeout: int = 120
    _health_check_interval: int = 2
    _memory_limit: str = "4g"

    def _get_container_config(self, device: str) -> dict:
        """
        Get Bridge-specific container configuration.

        :param device: Device string ('cpu', 'cuda:0', etc.).
        :return: Dictionary with environment variables, volumes, and device requests.
        """
        config = super()._get_container_config(device)
        config["environment"]["MUJOCO_GL"] = "egl"
        config["environment"]["PYOPENGL_PLATFORM"] = "egl"
        config["environment"]["SAPIEN_DISABLE_VULKAN_RAY_TRACING"] = 1
        config["environment"]["SAPIEN_DISABLE_VULKAN_RAY_QUERY"] = 1
        
        return config

    def list_tasks(self, suite: Optional[str] = None) -> dict:
        """
        List available Bridge tasks.
        
        Returns task information in two modes:
        1. Dynamic mode (if container running): Queries container for detailed
           task list including task names, indices, and instructions.
        2. Static mode (no container): Returns suite descriptions with counts.
        
        The dynamic mode provides complete task details by querying a running
        container's /tasks endpoint, which returns the full task registry.
        
        :param suite: Optional suite name to filter results (e.g., 'bridge').
        
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
                params["suite"] = "bridge"
                
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
            "bridge": {
                "description": "Tasks with the WidowX robot",
                "count": 4
            },
            "_note": "Start an env to get full task listings with instructions",
        }