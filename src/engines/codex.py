from __future__ import annotations

import os
import platform

from src.engines.base import Engine


class Engine(Engine):
    name = "codex"

    def _binary_names(self) -> list[str]:
        return ["codex"]

    def _search_paths(self) -> list[str]:
        home = os.path.expanduser("~")
        if platform.system() == "Windows":
            local = os.environ.get("LOCALAPPDATA", "")
            return [
                os.path.join(local, "codex", "codex.exe"),
            ]
        return [
            "/usr/local/bin/codex",
            os.path.join(home, ".local", "bin", "codex"),
            os.path.join(home, ".npm-global", "bin", "codex"),
        ]

    def _version_args(self) -> list[str]:
        return ["--version"]

    def _generate_args(self, model: str, budget_usd: float) -> list[str]:
        return ["exec", "--sandbox", "read-only", "-m", model]
