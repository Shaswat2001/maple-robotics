import docker
from typing import List, Dict
from vla.backend.envs.base import EnvBackend

class LiberoEnvBackend(EnvBackend):
    name = "libero"

    IMAGE = "shaswatai/robotics_envs:libero"
    RPC_PORT = 8000

    def __init__(self):
        self.client = docker.from_env()

    def pull(self) -> dict:

        try:
            image = self.client.images.pull(self.IMAGE)

            return {
                "env": self.name,
                "image": self.IMAGE
            }
        except docker.errors.APIError as e:
            raise RuntimeError(f"Error pulling image: {e}")
        except Exception as e:
            raise RuntimeError(f"An unexpected error occurred: {e}")
        
    def serve(self, num_envs: int) -> List[str]:
        handles = []
        for _ in range(num_envs):

            container = self.client.containers.run(
                self.IMAGE,
                detach=True,
                remove=True,
                ports={f"{self.RPC_PORT}/tcp": None},  # random host port
                labels={
                    "vla.env": self.name,
                },
            )

            container.reload()
            port_info = container.attrs["NetworkSettings"]["Ports"]
            # print(port_info)
            # host_port = int(port_info[f"{self.RPC_PORT}/tcp"][0]["HostPort"])

            handles.append({
                "container_id": container.id,
                # "host_port": host_port,
            })

        return handles

    def info(self) -> dict:
        return {
            "name": self.name,
            "type": "env",
            "tasks": ["PutCarrotOnPlateInScene-v0"],
        }

    def reset(self):
        print("[Libero] reset (stub)")
        return {"image": None}

    def step(self, action):
        print("[Libero] step (stub)", action)
        return {"image": None}, 0.0, True, {}
    
    def stop(self, handles: List[Dict]) -> None:
        for h in handles:
            try:
                container = self.client.containers.get(h["container_id"])
                container.stop()
            except docker.errors.NotFound:
                pass
