"""Adapter utilities.

This module contains adapters utilities needed to construct the necessary class.
"""

from .base import Adapter
from .registry import get_adapter, register, list_adapters

__all__ = ["Adapter", "get_adapter", "register", "list_adapters"]