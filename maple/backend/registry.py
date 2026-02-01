from maple.backend.policy.openvla import OpenVLAPolicy
from maple.backend.envs.libero import LiberoEnvBackend

ENV_BACKENDS = {
    "libero": LiberoEnvBackend,
}

POLICY_BACKENDS = {
    "openvla": OpenVLAPolicy,
}