import requests
from typing import Optional
from vla.backend.envs.base import EnvBackend
from vla.utils.logging import get_logger

log = get_logger("env.libero")

class LiberoEnvBackend(EnvBackend):
    """Backend for LIBERO manipulation environments."""
    
    name = "libero"
    IMAGE = "shaswatai/robotics_envs:libero"
    CONTAINER_PORT = 8000
    STARTUP_TIMEOUT = 120
    HEALTH_CHECK_INTERVAL = 2
    MEMORY_LIMIT = "4g"
    
    def _get_container_config(self) -> dict:
        """LIBERO-specific container configuration."""
        return {
            "environment": {
                "MUJOCO_GL": "osmesa",
            },
            "volumes": {},
            "device_requests": [],
        }
    
    def list_tasks(self, suite: Optional[str] = None) -> dict:
        """List available LIBERO tasks."""
        # If we have an active handle, use it to get dynamic task list
        if self._active_handles:
            handle = next(iter(self._active_handles.values()))
            base_url = self._get_base_url(handle)
            
            try:
                params = {}
                if suite:
                    params["suite"] = suite
                    
                resp = requests.get(f"{base_url}/tasks", params=params, timeout=30)
                resp.raise_for_status()
                return resp.json()
                
            except requests.exceptions.RequestException:
                pass
        
        # Fallback: return static task suite info
        return {
            "libero_spatial": {"description": "10 spatial reasoning tasks", "count": 10},
            "libero_object": {"description": "10 object manipulation tasks", "count": 10},
            "libero_goal": {"description": "10 goal-conditioned tasks", "count": 10},
            "libero_10": {"description": "10 diverse tasks", "count": 10},
            "libero_90": {"description": "90 diverse tasks", "count": 90},
            "_note": "Start an env to get full task listings with instructions",
        }
