from __future__ import annotations

import os
import platform

from src.engines.base import Engine


class Engine(Engine):
    name = "agy"

    def _binary_names(self) -> list[str]:
        return ["agy"]

    def _search_paths(self) -> list[str]:
        home = os.path.expanduser("~")
        if platform.system() == "Windows":
            local = os.environ.get("LOCALAPPDATA", "")
            return [os.path.join(local, "agy", "agy.exe")]
        return [
            "/usr/local/bin/agy",
            os.path.join(home, ".local", "bin", "agy"),
            os.path.join(home, ".npm-global", "bin", "agy"),
        ]

    def _version_args(self) -> list[str]:
        return ["--version"]

    def _generate_args(self, model: str) -> list[str]:
        return ["--model", model, "-p"]
