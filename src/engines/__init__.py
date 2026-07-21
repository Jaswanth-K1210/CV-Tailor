from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.engines.base import Engine

ENGINE_MAP: dict[str, str] = {
    "claude": "src.engines.claude",
    "gemini": "src.engines.gemini",
    "codex": "src.engines.codex",
}

ENGINE_LABELS: dict[str, str] = {
    "claude": "Claude Code",
    "gemini": "Gemini CLI",
    "codex": "Codex CLI",
}

DEFAULT_MODELS: dict[str, str] = {
    "claude": "sonnet",
    "gemini": "gemini-2.5-flash",
    "codex": "gpt-5.4",
}


def get_engine(name: str) -> Engine:
    if name not in ENGINE_MAP:
        raise ValueError(f"Unknown engine: {name!r}. Choose from: {list(ENGINE_MAP)}")
    module = importlib.import_module(ENGINE_MAP[name])
    return module.Engine()


def available_engines() -> list[dict[str, str]]:
    results = []
    for name, module_path in ENGINE_MAP.items():
        try:
            mod = importlib.import_module(module_path)
            eng = mod.Engine()
            info = eng.check()
            results.append({
                "name": name,
                "label": ENGINE_LABELS[name],
                "available": info["ok"],
                "version": info.get("version", ""),
                "default_model": DEFAULT_MODELS[name],
            })
        except Exception:
            results.append({
                "name": name,
                "label": ENGINE_LABELS[name],
                "available": False,
                "version": "",
                "default_model": DEFAULT_MODELS[name],
            })
    return results
