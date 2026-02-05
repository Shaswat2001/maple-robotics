"""
Miscellaneous utility functions for the MAPLE CLI.

This module provides helper functions used across various CLI commands,
including URL construction for daemon communication and parsing of
shorthand specifications.

Key utilities:
- daemon_url: Construct daemon endpoint URLs
- parse_policy_env: Parse policy@env shorthand notation
"""

import typer 
from typing import Tuple

def daemon_url(port: int):
    """
    Construct the daemon API base URL.
    
    Builds the HTTP URL for communicating with the MAPLE daemon API
    based on the provided port number. The daemon always runs on
    localhost (0.0.0.0).
    
    :param port: Port number where the daemon is listening.
    :return: Full base URL for daemon API requests.
    """
    return f"http://0.0.0.0:{port}"

def parse_policy_env(spec: str) -> Tuple[str, str]:
    """
    Parse policy@env shorthand specification.
    
    Parses a combined policy and environment specification in the format
    'policy@env' and returns the individual components. This shorthand
    format is used for convenience in CLI commands that need both a
    policy and environment.
    
    :param spec: Specification string in format 'policy@env'.
    :return: Tuple of (policy_name, env_name) extracted from the spec.
    """
    # Check for required '@' separator
    if "@" not in spec:
        raise typer.BadParameter("Expected POLICY@ENV (example: openvla@libero)")
    
    # Split on first '@' only (in case names contain '@')
    policy, env = spec.split("@", 1)
    
    # Strip whitespace from both components
    policy, env = policy.strip(), env.strip()
    
    # Validate that both components are non-empty
    if not policy or not env:
        raise typer.BadParameter("Invalid POLICY@ENV")
    
    return policy, env