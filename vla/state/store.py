import json
from pathlib import Path

STATE_DIR = Path.home() / ".vla"
STATE_FILE = STATE_DIR / "state.json"

DEFAULT_STATE = {
    "policies": [],
    "envs": [],
    "served_policies": [],
    "served_envs": {},   # name -> num_envs
}


def load_state() -> dict:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    if not STATE_FILE.exists():
        save_state(DEFAULT_STATE)
    with open(STATE_FILE, "r") as f:
        return json.load(f)


def save_state(state: dict):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)