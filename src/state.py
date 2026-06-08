import json
from pathlib import Path
from typing import Dict


STATE_FILE = Path("state/last_alert.json")


def load() -> Dict[str, float]:
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def save(state: Dict[str, float]) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2, sort_keys=True))


def alert_key(game_id: str, site: str, level: str) -> str:
    return f"{game_id}|{site}|{level}"
