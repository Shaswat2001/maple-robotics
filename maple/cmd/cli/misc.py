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

def daemon_url(port: int) -> str:
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
    
    Example:
        'openvla@libero' -> ('openvla', 'libero')
    
    :param spec: Specification string in format 'policy@env'.
    
    :return: Tuple of (policy_name, env_name) extracted from the spec.
    
    :raises typer.BadParameter: If the spec doesn't contain '@' separator
                                or if either component is empty.
    """
    # Check for required '@' separator
    if "@" not in spec:
        raise typer.BadParameter("Expected POLICY@ENV