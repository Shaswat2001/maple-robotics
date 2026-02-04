from __future__ import annotations

def parse_versioned(spec: str) -> tuple[str, str]:
    """
    Parse a versioned specification string into name and version components.
    
    Splits a colon-separated specification into its name and version parts.
    If no version is specified, defaults to 'latest'. Used for parsing
    model specifications, package versions, or other versioned identifiers.

    param: spec: Versioned specification string in format 'name:version' or 'name'.
    return: Tuple of (name, version) where version is 'latest' if not specified.
    """
    spec = spec.strip()
    if ":" in spec:
        name, ver = spec.split(":", 1)
        name, ver = name.strip(), ver.strip()
        if not name or not ver:
            raise ValueError(f"Invalid spec: {spec}")
        return name, ver
    return spec, "latest"
