from __future__ import annotations

import os
import platform

from src.engines.base import Engine


class Engine(Engine):
    name = "opencode"

    def _binary_names(self) -> list[str]:
        return ["opencode"]

    def _search_paths(self) -> list[str]:
        home = os.path.expanduser("~")
        if platform.system() == "Windows":
            local = os.environ.get("LOCALAPPDATA", "")
            return [
                os.path.join(local, "opencode", "opencode.exe"),
                os.path.join(home, ".opencode", "bin", "opencode.exe"),
            ]
        return [
            "/usr/local/bin/opencode",
            "/opt/homebrew/bin/opencode",
            os.path.join(home, ".local", "bin", "opencode"),
            os.path.join(home, ".opencode", "bin", "opencode"),
            os.path.join(home, ".npm-global", "bin", "opencode"),
        ]

    def _version_args(self) -> list[str]:
        return ["--version"]

    def _generate_args(self, model: str) -> list[str]:
        return ["run", "-m", model]

    def _send_prompt_via_stdin(self) -> bool:
        return False
