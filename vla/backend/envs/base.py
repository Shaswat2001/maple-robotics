# vla/envs/base.py
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

@dataclass
class EnvHandle:
    env_id: str
    backend_name: str
    host: str
    port: str
    container_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "env_id": self.env_id,
            "backend_name": self.backend_name,
            "host": self.host,
            "port": self.port,
            "container_id": self.container_id,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, d: dict) -> "EnvHandle":
        return cls(**d)

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
    def stop(self, handles: List[EnvHandle]) -> None:
        """Stop runtime env instances"""
        pass

    @abstractmethod
    def setup(self, handle: EnvHandle, task: str, seed: Optional[int] = None) -> Dict:
        pass

    @abstractmethod
    def reset(self, handle: EnvHandle, seed: Optional[int] = None) -> Dict:
        pass
    
    @abstractmethod
    def step(self, handle: EnvHandle, action: List[float]) -> Dict:
        pass

    @abstractmethod
    def get_info(self, handle: EnvHandle) -> Dict:
        pass

    @abstractmethod
    def list_tasks(self, suite: Optional[str] = None) -> Dict:
        pass