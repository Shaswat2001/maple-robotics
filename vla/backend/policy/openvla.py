import uuid
import time
import requests
from pathlib import Path
from typing import List, Optional, Dict, Any

import docker
from docker.errors import NotFound, APIError
from vla.backend.policy.base import PolicyBackend, PolicyHandle
from huggingface_hub import snapshot_download

class OpenVLAPolicy(PolicyBackend):
    name = "openvla"

    IMAGE = "shaswatai/robotics_vla:openvla"
    CONTAINER_PORT = 8000
    STARTUP_TIMEOUT = 300
    HEALTH_CHECK_INTERVAL = 5

    HF_REPOS = {
        "7b": "openvla/openvla-7b",
        "latest": "openvla/openvla-7b",
    }    

    def info(self) -> dict:
        return {
            "name": self.name,
            "type": "policy",
            "inputs": ["image", "instruction"],
            "outputs": ["action"],
            "versions": list(self.HF_REPOS.keys()),
            "image": self.IMAGE,
        }
    
    def pull(self, version: str, dst: Path) -> dict:
        repo = self.HF_REPOS.get(version)
        if repo is None:
            raise ValueError(f"Unknown version '{version}' for {self.name}")

        dst.mkdir(parents=True, exist_ok=True)

        print(f"[OpenVLA] Downloading {repo} to {dst}...")

        snapshot_download(
            repo_id=repo,
            local_dir=dst,
            local_dir_use_symlinks=False,
        )

        return {
            "name": self.name,
            "version": version,
            "source": "huggingface",
            "repo": repo,
            "path": str(dst),
        }
    
    def pull_image(self) -> Dict:
        
        try:
            image = self.client.images.pull(self.IMAGE)
            return {"image": self.IMAGE, "source": "pulled"}
        except APIError:
            pass
        
        try:
            image = self.client.images.get(self.IMAGE)
            return {"image": self.IMAGE, "source": "local"}
        except NotFound:
            raise RuntimeError(
                f"Image {self.IMAGE} not found. "
                f"Build it with: docker build -t {self.IMAGE} docker/openvla/"
            )

    def serve(self,
              version: str,
              model_path: Path,
              device: str,
              host_port: Optional[int] = None,
              attn_implementation: str = "sdpa"):
        
        policy_id = f"openvla-{version}-{uuid.uuid4().hex[:8]}"
        if host_port is not None:
            port_mapping = {f"{self.CONTAINER_PORT}/tcp": host_port}
        else:
            port_mapping = {f"{self.CONTAINER_PORT}/tcp": None}

        device_request = []
        gpu_idx = "0"
        if device.startswith("cuda"):
            gpu_idx = device.split(":")[-1] if ":" in device else "0"
            device_requests = [
                docker.types.DeviceRequest(
                    device_ids=[gpu_idx],
                    capabilities=[["gpu"]]
                )
            ]

        try:
            container = self.client.containers.run(
                self.IMAGE,
                detach=True,
                remove=True,
                name=policy_id,
                ports=port_mapping,
                volumes={
                    str(model_path.absolute()): {
                        "bind": "/models/weights",
                        "mode": "ro",  # Read-only mount
                    }
                },
                device_requests=device_requests,
                environment={
                    "CUDA_VISIBLE_DEVICES": gpu_idx if device.startswith("cuda") else "",
                    "ATTN_IMPLEMENTATION": attn_implementation,
                },
                labels={
                    "vla.policy": self.name,
                    "vla.policy_id": policy_id,
                    "vla.version": version,
                },
                # Resource limits
                mem_limit="32g",
                shm_size="2g",
            )

            actual_port = None
            for _ in range(10):
                container.reload()
                port_info = container.attrs["NetworkSettings"]["Ports"]
                port_key = f"{self.CONTAINER_PORT}/tcp"
                
                if port_info and port_key in port_info and port_info[port_key]:
                    actual_port = int(port_info[port_key][0]["HostPort"])
                    break
                
                time.sleep(0.5)
    
            if actual_port is None:
                raise RuntimeError(f"Could not get port mapping for container {policy_id}")

            handle = PolicyHandle(
                policy_id= policy_id, 
                backend_name= self.name,
                version=version,
                host= "127.0.0.1",
                port= actual_port,
                container_id= container.id,
                model_path= str(model_path),
                device= device,
                metadata= {
                    "status": "starting",
                    "attn_implementation": attn_implementation
                }
            )

            print(f"[OpenVLA] Waiting for container {policy_id} to start...")
            if not self.wait_for_ready(handle):
                try:
                    container.stop(timeout=10)
                except Exception:
                    pass
                raise RuntimeError(f"Container {policy_id} failed to start within {self.STARTUP_TIMEOUT}s")
            
            # Load model (weights are at /models/weights inside container)
            print(f"[OpenVLA] Loading model on {device} with {attn_implementation} attention...")
            base_url = self._get_base_url(handle)
            resp = requests.post(
                f"{base_url}/load",
                json={
                    "model_path": "/models/weights",
                    "device": device,
                    "attn_implementation": attn_implementation,
                },
                timeout=self.STARTUP_TIMEOUT,
            )
            
            if resp.status_code != 200:
                try:
                    container.stop(timeout=10)
                except Exception:
                    pass
                raise RuntimeError(f"Failed to load model: {resp.json().get('detail', resp.text)}")
            
            handle.metadata["status"] = "ready"
            self._active_handles[policy_id] = handle
            
            print(f"[OpenVLA] Policy {policy_id} ready on port {actual_port}")
            return handle
        
        except Exception as e:
            raise RuntimeError(f"Failed to serve policy: {e}")

    def act(
        self, 
        handle: PolicyHandle, 
        image: Any, 
        instruction: str,
        unnorm_key: Optional[str] = None,
    ) -> List[float]:
        """Get action for a single observation."""
        base_url = self._get_base_url(handle)
        
        payload = {
            "image": self._encode_image(image),
            "instruction": instruction,
        }
        if unnorm_key:
            payload["unnorm_key"] = unnorm_key
        
        try:
            resp = requests.post(f"{base_url}/act", json=payload, timeout=30)
            resp.raise_for_status()
            return resp.json()["action"]
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Failed to get action: {e}")
    
    def act_batch(
        self,
        handle: PolicyHandle,
        images: List[Any],
        instructions: List[str],
        unnorm_key: Optional[str] = None
    ) -> List[List[float]]:
        """Get actions for a batch of observations."""
        base_url = self._get_base_url(handle)
        
        payload = {
            "images": [self._encode_image(img) for img in images],
            "instructions": instructions,
        }
        if unnorm_key:
            payload["unnorm_key"] = unnorm_key
        
        try:
            resp = requests.post(f"{base_url}/act_batch", json=payload, timeout=60)
            resp.raise_for_status()
            return resp.json()["actions"]
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Failed to get batch actions: {e}")
