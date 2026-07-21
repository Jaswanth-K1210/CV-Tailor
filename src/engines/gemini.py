from __future__ import annotations

import os
import platform

from src.engines.base import Engine


class Engine(Engine):
    name = "gemini"

    def _binary_names(self) -> list[str]:
        return ["gemini"]

    def _search_paths(self) -> list[str]:
        home = os.path.expanduser("~")
        if platform.system() == "Windows":
            local = os.environ.get("LOCALAPPDATA", "")
            return [os.path.join(local, "gemini", "gemini.exe")]
        return [
            "/usr/local/bin/gemini",
            "/opt/homebrew/bin/gemini",
            os.path.join(home, ".local", "bin", "gemini"),
            os.path.join(home, ".npm-global", "bin", "gemini"),
        ]

    def _version_args(self) -> list[str]:
        return ["--version"]

    def _generate_args(self, model: str) -> list[str]:
        return ["-p", "-m", model]
