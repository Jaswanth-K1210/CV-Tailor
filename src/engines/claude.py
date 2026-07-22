from __future__ import annotations

import os
import platform

from src.engines.base import Engine


class Engine(Engine):
    name = "claude"

    def _binary_names(self) -> list[str]:
        return ["claude"]

    def _search_paths(self) -> list[str]:
        home = os.path.expanduser("~")
        if platform.system() == "Windows":
            local = os.environ.get("LOCALAPPDATA", "")
            return [os.path.join(local, "claude", "claude.exe")]
        return [
            "/usr/local/bin/claude",
            os.path.join(home, ".local", "bin", "claude"),
            os.path.join(home, ".npm-global", "bin", "claude"),
        ]

    def _version_args(self) -> list[str]:
        return ["--version"]

    def _generate_args(self, model: str) -> list[str]:
        return ["-p", "--model", model]

    def _send_prompt_via_stdin(self) -> bool:
        return True
