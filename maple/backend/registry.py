"""
Policy and Environment Backend Registry

POLICY_BACKENDS: Simple dict mapping "policy" → Policy backend class.
ENV_BACKENDS: Simple dict mapping "env" → Environment backend class.
"""

from .policy import OpenVLAPolicy, SmolVLAPolicy, OpenPIPolicy
from .envs import LiberoEnvBackend, RoboCasaEnvBackend

ENV_BACKENDS = {
    "libero": LiberoEnvBackend,
    "robocasa": RoboCasaEnvBackend
}

POLICY_BACKENDS = {
    "openvla": OpenVLAPolicy,
    "smolvla": SmolVLAPolicy,
    "openpi": OpenPIPolicy
}