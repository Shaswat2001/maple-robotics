"""
Adapter Registry

Simple dict mapping "policy:env" → Adapter class.
To add a new adapter, call the register function with Adapter class and policy:env string.
"""

from typing import Dict, Type, Any, List
from maple.adapters.custom import OpenVLALiberoAdapter, SmolVLALiberoAdapter, OpenPILiberoAdapter, OpenPIAlohaSimAdapter
from maple.adapters.base import Adapter

# Global registry
ADAPTERS: Dict[str, Adapter] = {
    "openvla:libero": OpenVLALiberoAdapter,
    "smolvla:libero": SmolVLALiberoAdapter,
    "openpi:libero": OpenPILiberoAdapter,
    "openpi:alohasim": OpenPIAlohaSimAdapter
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
    
    return _IdentityAdapter(policy, env)
    
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


class _IdentityAdapter(Adapter):
    """Pass-through; tries common image keys, returns action unchanged."""

    _common_image_keys = ["agentview_image", "image", "rgb", "pixels", "agentview_rgb"]

    def __init__(self, policy: str = "unknown", env: str = "unknown"):
        super().__init__()
        self.name = f"identity-{policy}-{env}"
        self.policy = policy
        self.env = env

    def transform_obs(self, raw_obs: Dict[str, Any]) -> Dict[str, Any]:
        """Method to transform libero observation to openVLA input

        :param raw_obs: Raw observation from libero
        :return: Tranformed observatation as needed by openVLA
        """
        for key in self._common_image_keys:
            if key in raw_obs:
                return {"image": self.decode_image(raw_obs[key])}
        raise KeyError(f"No image key found in obs. Keys: {list(raw_obs.keys())}")
        
    def transform_action(self, raw_action: List[float]) -> List[float]:
        """Method to transform openVLA output to libero action.
        
        :param raw_action: Raw output from openVLA.
        :return: Tranformed action needed by the libero.
        """
        return raw_action
