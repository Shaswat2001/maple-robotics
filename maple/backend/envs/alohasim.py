"""
AlohaSim environment backend.

This module implements the environment backend for AlohaSim, 
a suite of sim environment for the Aloha robot. It includes a collection of tasks for robot learning and evaluation.

AlohaSim provides multiple task suites:
- basic: 5 basic manipulation tasks
- instruction: 12 tasks in which instructions are followed
- dexterous: 3 dexterous tasks

The backend handles Docker container management and provides task enumeration
both statically (when no container is running) and dynamically (by querying
a running container for detailed task information).
"""

import requests
from typing import Optional

from maple.backend.envs.base import EnvBackend
from maple.utils.logging import get_logger

log = get_logger("env.alohasim")

class AlohaSimBackend(EnvBackend):
    """
    Backend for AlohaSim manipulation environments.
    
    Manages AlohaSim environment containers with MuJoCo physics simulation
    using EGL for headless rendering. Provides access to multiple task
    suites with language-conditioned manipulation tasks.
    
    The backend uses the maplerobotics/alohasim:latest Docker image which
    includes AlohaSim, MuJoCo, and all necessary dependencies pre-configured.
    """
    
    name = "alohasim"
    _image = "maplerobotics/alohasim:latest"
    _container_port: int = 8000
    _startup_timeout: int = 120
    _health_check_interval: int = 2
    _memory_limit: str = "4g"

    def _get_container_config(self, device: str) -> dict:
        """
        Get AlohaSim-specific container configuration.

        :param device: Device string ('cpu', 'cuda:0', etc.).
        :return: Dictionary with environment variables, volumes, and device requests.
        """
        config = super()._get_container_config(device)
        config["environment"]["MUJOCO_GL"] = "egl"
        config["environment"]["PYOPENGL_PLATFORM"] = "egl"
        
        return config

    def list_tasks(self, suite: Optional[str] = None) -> dict:
        """
        List available AlohaSim tasks.
        
        Returns task information in two modes:
        1. Dynamic mode (if container running): Queries container for detailed
           task list including task names, indices, and instructions.
        2. Static mode (no container): Returns suite descriptions with counts.
        
        The dynamic mode provides complete task details by querying a running
        container's /tasks endpoint, which returns the full task registry.
        
        :param suite: Optional suite name to filter results (e.g., 'basic').
        
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
            "basic": {
                "description": "Basic manipulation tasks",
                "count": 5
            },
            "instruction": {
                "description": "Tasks in which instructions are followed",
                "count": 12
            },
            "dexterous": {
                "description": "Complex dexterous tasks",
                "count": 3
            },
            "_note": "Start an env to get full task listings with instructions",
        }