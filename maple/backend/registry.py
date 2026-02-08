"""
Policy and Environment Backend Registry

POLICY_BACKENDS: Simple dict mapping "policy" → Policy backend class.
ENV_BACKENDS: Simple dict mapping "env" → Environment backend class.
"""

from .policy import OpenVLAPolicy, SmolVLAPolicy, OpenPIPolicy
from .envs import LiberoEnvBackend, RoboCasaEnvBackend, FractalBackend, BridgeBackend, AlohaSimBackend

ENV_BACKENDS = {
    "libero": LiberoEnvBackend,
    "robocasa": RoboCasaEnvBackend,
    "bridge": BridgeBackend,
    "fractal": FractalBackend,
    "alohasim": AlohaSimBackend
}

POLICY_BACKENDS = {
    "openvla": OpenVLAPolicy,
    "smolvla": SmolVLAPolicy,
    "openpi": OpenPIPolicy
}