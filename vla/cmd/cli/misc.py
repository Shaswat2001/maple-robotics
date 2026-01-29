import typer 
from typing import Tuple

def daemon_url(port: int):
    return f"http://0.0.0.0:{port}"

def parse_policy_env(spec: str) -> Tuple[str, str]:
    """
    Parses 'policy@env' shorthand. Example: 'openvla@libero'
    """

    if "@" not in spec:
        raise typer.BadParameter("Expected POLICY@ENV (example: openvla@libero)")
    
    policy, env = spec.split("@", 1)
    policy, env = policy.strip(), env.strip()
    if not policy or not env:
        raise typer.BadParameter("Invalid POLICY@ENV")
    return policy, env