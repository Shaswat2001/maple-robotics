from __future__ import annotations

def parse_versioned(spec: str) -> tuple[str, str]:
    """
    'openvla:7b' -> ('openvla', '7b')
    'openvla'    -> ('openvla', 'latest')
    """
    spec = spec.strip()
    if ":" in spec:
        name, ver = spec.split(":", 1)
        name, ver = name.strip(), ver.strip()
        if not name or not ver:
            raise ValueError(f"Invalid spec: {spec}")
        return name, ver
    return spec, "latest"
