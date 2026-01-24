from abc import ABC, abstractmethod
from pathlib import Path

class PolicyBackend(ABC):
    name: str

    @abstractmethod
    def info(self) -> dict:
        pass

    @abstractmethod
    def load(self, version: str, model_path: Path, device: str) -> None:
        pass

    @abstractmethod
    def pull(self, version: str, dst: Path) -> dict:
        """Download model artifacts into dst"""
        pass


    @abstractmethod
    def act(self, observation: dict) -> dict:
        pass

