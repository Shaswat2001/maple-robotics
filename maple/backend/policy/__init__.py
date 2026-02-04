"""
Policy Backend

Backend classes for different policies available in MAPLE
"""

from .openvla import OpenVLAPolicy
from .smolvla import SmolVLAPolicy

__all__ = ["OpenVLAPolicy", "SmolVLAPolicy"]