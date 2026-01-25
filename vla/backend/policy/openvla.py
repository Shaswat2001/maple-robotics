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
    
    def load(self, version: str, model_path: Path, device: str) -> None:
        # Torch init stub: proves GPU/CPU device wiring works
        # if device.startswith("cuda") and not torch.cuda.is_available():
        #     raise RuntimeError("CUDA device requested but torch.cuda.is_available() is False")

        # # Allocate something tiny on target device
        # _ = torch.zeros(1, device=device)

        # NOTE: real load later:
        # - load config/tokenizer
        # - load weights
        # - set eval mode, etc.
        print(f"[OpenVLA] load stub OK: version={version} path={model_path} device={device}")

    def act(self, observation: dict) -> dict:
        # dummy action
        return {"action": [0.0, 0.0, 0.0]}
