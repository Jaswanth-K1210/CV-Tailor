from __future__ import annotations

import json
from pathlib import Path

_DIR = Path.home() / ".cv-tailor"
_FILE = _DIR / "settings.json"

_DEFAULTS = {
    "engine": "claude",
    "model": "sonnet",
    "max_generations": 6,
}


def _ensure_dir():
    _DIR.mkdir(parents=True, exist_ok=True)


def load() -> dict:
    if _FILE.exists():
        try:
            data = json.loads(_FILE.read_text())
            merged = {**_DEFAULTS, **data}
            return merged
        except (json.JSONDecodeError, OSError):
            pass
    return dict(_DEFAULTS)


def save(settings: dict) -> None:
    _ensure_dir()
    merged = {**_DEFAULTS, **settings}
    _FILE.write_text(json.dumps(merged, indent=2))


def get(key: str, default=None):
    return load().get(key, default)


def set(key: str, value) -> None:
    data = load()
    data[key] = value
    save(data)
