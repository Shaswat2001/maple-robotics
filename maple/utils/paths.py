from pathlib import Path

VLA_HOME = Path.home() / ".maple"

def policy_dir(name: str, version: str) -> Path:
    return VLA_HOME / "models" / name / version