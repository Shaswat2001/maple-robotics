from typing import Dict, Type
from maple.adapters.custom import OpenVLALiberoAdapter, SmolVLALiberoAdapter
from maple.adapters.base import Adapter

# Global registry
ADAPTERS: Dict[str, Adapter] = {
    "openvla:libero": OpenVLALiberoAdapter,
    "smolvla:libero": SmolVLALiberoAdapter
}

def get_adapter(policy: str, env: str) -> Adapter:
    """
    Get adapter given the policy and environment name.

    :param policy: policy name
    :param env: environment name
    :return: Adapter class given the policy:env input
    """

    key = f"{policy}:{env}"
    if key in ADAPTERS:
        return ADAPTERS[key]()
    
    # strip version
    base = policy.split(":")[0] if ":" in policy else policy
    key_base = f"{base}:{env}"
    if key_base in ADAPTERS:
        return ADAPTERS[key_base]()
    
def register(policy: str, env: str, cls: Type[Adapter]) -> None:
    """Register an adapter class at runtime.
    
    :param policy: policy name
    :param env: environment name
    :param cls: Adapter class for registry
    """
    ADAPTERS[f"{policy}:{env}"] = cls


def list_adapters() -> Dict[str, dict]:
    """Return info for every registered adapter.
    
    :return Adapter class for registry
    """
    return {k: cls().get_info() for k, cls in ADAPTERS.items()}
