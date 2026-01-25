# vla/envs/base.py
from abc import ABC, abstractmethod
from typing import Any

class EnvBackend(ABC):
    name: str

    @abstractmethod
    def pull(self) -> dict:
        """Ensure env artifacts (e.g. docker image) exist"""
        pass

    @abstractmethod
    def serve(self, num_envs: int) -> list[Any]:
        """Start runtime env instances and return handles"""
        pass

    @abstractmethod
    def stop(self, handles: list[Any]) -> None:
        """Stop runtime env instances"""
        pass
