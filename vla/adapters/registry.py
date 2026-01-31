from typing import Dict, Type
from vla.adapters.custom import OpenVLALiberoAdapter
from vla.adapters.base import Adapter

# Global registry
ADAPTERS: Dict[str, Adapter] = {
    "openvla:libero": OpenVLALiberoAdapter
}

def get_adapter(policy: str, env: str) -> Adapter:

    key = f"{policy}:{env}"
    if key in ADAPTERS:
        return ADAPTERS[key]()
    
    # strip version
    base = policy.split(":")[0] if ":" in policy else policy
    key_base = f"{base}:{env}"
    if key_base in ADAPTERS:
        return ADAPTERS[key_base]()
    
def register(policy: str, env: str, cls: Type[Adapter]):
    """Register an adapter class at runtime."""
    ADAPTERS[f"{policy}:{env}"] = cls


def list_adapters() -> Dict[str, dict]:
    """Return info for every registered adapter."""
    return {k: cls().get_info() for k, cls in ADAPTERS.items()}
