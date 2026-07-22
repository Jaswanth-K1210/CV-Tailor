from __future__ import annotations

import os
import platform

from src.engines.base import Engine


class Engine(Engine):
    """Local models via Ollama.

    Caution: runs entirely on the user's machine. The selected model must be
    pulled first (`ollama pull <model>`) and generation can be slow on CPU or
    with large models.
    """

    name = "ollama"

    def _binary_names(self) -> list[str]:
        return ["ollama"]

    def _search_paths(self) -> list[str]:
        home = os.path.expanduser("~")
        if platform.system() == "Windows":
            local = os.environ.get("LOCALAPPDATA", "")
            return [os.path.join(local, "Programs", "Ollama", "ollama.exe")]
        return [
            "/usr/local/bin/ollama",
            "/opt/homebrew/bin/ollama",
            os.path.join(home, ".local", "bin", "ollama"),
        ]

    def _version_args(self) -> list[str]:
        return ["--version"]

    def _generate_args(self, model: str) -> list[str]:
        # `ollama run <model>` reads the prompt from stdin and prints the
        # response, then exits. No extra flags needed for a one-shot generation.
        return ["run", model]

    def _send_prompt_via_stdin(self) -> bool:
        return True
