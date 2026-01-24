from pathlib import Path
from vla.backend.policy.base import PolicyBackend
from huggingface_hub import snapshot_download

class OpenVLAPolicy(PolicyBackend):
    name = "openvla"
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
            "backend": "stub",
        }
    
    def pull(self, version: str, dst: Path) -> dict:
        repo = self.HF_REPOS.get(version)
        if repo is None:
            raise ValueError(f"Unknown version '{version}' for {self.name}")

        dst.mkdir(parents=True, exist_ok=True)

        # Minimal real pull (HF snapshot). Add dependency: huggingface_hub
        from huggingface_hub import snapshot_download
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

    def load(self):
        # later: load model weights
        print("[OpenVLA] loaded (stub)")

    def act(self, observation: dict) -> dict:
        # dummy action
        return {"action": [0.0, 0.0, 0.0]}
