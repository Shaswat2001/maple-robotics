"""
Miscellaneous utility functions for the MAPLE CLI.

This module provides helper functions used across various CLI commands,
including URL construction for daemon communication and parsing of
shorthand specifications.

Key utilities:
- daemon_url: Construct daemon endpoint URLs
- parse_policy_env: Parse policy@env shorthand notation
- parse_error_response: Parse response JSON in case of error
- load_kwargs: Load string kwargs properly into dict
"""

import json
import typer 
from typing import Tuple, Dict

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

def parse_error_response(resp) -> str:
    """Parse error response, handling JSON, XML, and plain text."""
    # Try JSON first
    try:
        data = resp.json()
        if isinstance(data, dict):
            return data.get("detail") or data.get("error") or data.get("message") or str(data)
        return str(data)
    except Exception:
        pass
    
    text = resp.text
    
    # Try XML parsing
    if text.strip().startswith("<?xml") or text.strip().startswith("<"):
        try:
            import xml.etree.ElementTree as ET
            root = ET.fromstring(text)
            
            # Common XML error fields
            for tag in ["Message", "message", "Detail", "detail", "Error", "error"]:
                elem = root.find(f".//{tag}")
                if elem is not None and elem.text:
                    return elem.text
            
            # Try to get Code + Message combo
            code = root.findtext(".//Code") or root.findtext(".//code")
            msg = root.findtext(".//Message") or root.findtext(".//message")
            if code and msg:
                return f"{code}: {msg}"
            if msg:
                return msg
            if code:
                return code
                
        except ET.ParseError:
            pass
    
    # Fallback: clean up raw text
    return text.strip()[:500]  # Truncate long responses

def load_kwargs(kwargs: str) -> Dict:
    """Helper function to load string kwargs to a dictionary"""

    if kwargs:
        try:
            kwargs = json.loads(kwargs)
            if not isinstance(kwargs, dict):
                print(f"[red]Error:[/red] {kwargs} must be a JSON object/dict")
                raise typer.Exit(1)
        except json.JSONDecodeError as e:
            print(f"[red]Error:[/red] Invalid JSON: {e}")
            raise typer.Exit(1)
    else:
        kwargs = {}

    return kwargs