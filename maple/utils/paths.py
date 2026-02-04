from pathlib import Path

VLA_HOME = Path.home() / ".maple"

def policy_dir(name: str, version: str) -> Path:
    """
    Get the directory path for a specific policy model version.
    
    Constructs the filesystem path where a particular model version is stored
    within the MAPLE models directory structure.
    
    :param name: Name of the policy model.
    :param version: Version identifier of the policy model.
    :return: Path object pointing to the model's version directory.
    """
    return VLA_HOME / "models" / name / version