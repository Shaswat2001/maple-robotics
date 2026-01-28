from vla.backend.policy.openvla import OpenVLAPolicy
from vla.backend.envs.libero import LiberoEnvBackend

ENV_BACKENDS = {
    "libero": LiberoEnvBackend,
}

POLICY_BACKENDS = {
    "openvla": OpenVLAPolicy,
}