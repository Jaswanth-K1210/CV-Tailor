from __future__ import annotations

import os
import platform
import shutil
import subprocess
from abc import ABC, abstractmethod


class Engine(ABC):
    name: str = "base"

    @abstractmethod
    def _binary_names(self) -> list[str]:
        """Return possible binary names (e.g. ['claude', 'claude.exe'])."""

    @abstractmethod
    def _search_paths(self) -> list[str]:
        """Return platform-specific paths to check beyond PATH."""

    @abstractmethod
    def _version_args(self) -> list[str]:
        """Return CLI args to get version info."""

    @abstractmethod
    def _generate_args(self, model: str) -> list[str]:
        """Return CLI args for headless generation."""

    def _send_prompt_via_stdin(self) -> bool:
        """Override to True if the CLI reads prompt from stdin (default: pass as arg)."""
        return False

    def _extra_paths(self) -> list[str]:
        paths = []
        home = os.path.expanduser("~")
        for sub in (".npm-global/bin", ".local/bin", "node_modules/.bin"):
            paths.append(os.path.join(home, sub))
        for prefix in ("/usr/local/bin", "/opt/homebrew/bin"):
            if prefix not in paths:
                paths.append(prefix)
        return paths

    def _shell_which(self, name: str) -> str | None:
        try:
            shell = os.environ.get("SHELL", "/bin/zsh")
            r = subprocess.run(
                [shell, "-l", "-c", f"which {name}"],
                capture_output=True, text=True, timeout=5,
            )
            if r.returncode == 0:
                path = r.stdout.strip()
                if path and os.path.isfile(path):
                    return path
        except Exception:
            pass
        return None

    def find_binary(self) -> str | None:
        system = platform.system()
        for name in self._binary_names():
            path = shutil.which(name)
            if path:
                return path
        for name in self._binary_names():
            path = self._shell_which(name)
            if path:
                return path
        for base_path in self._search_paths() + self._extra_paths():
            candidates = [base_path]
            if system == "Windows":
                candidates.append(base_path + ".exe")
            for candidate in candidates:
                if os.path.isfile(candidate):
                    return candidate
        return None

    def check(self) -> dict:
        binary = self.find_binary()
        if not binary:
            return {"ok": False, "error": f"{self.name} CLI not found"}
        try:
            r = subprocess.run(
                [binary] + self._version_args(),
                capture_output=True, text=True, timeout=15,
            )
            version = r.stdout.strip() or r.stderr.strip()
            return {"ok": r.returncode == 0, "version": version}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def generate(self, prompt: str, model: str, timeout: int = 120) -> str:
        binary = self.find_binary()
        if not binary:
            raise RuntimeError(f"{self.name} CLI not found")
        args = [binary] + self._generate_args(model)
        if self._send_prompt_via_stdin():
            result = subprocess.run(
                args, input=prompt, capture_output=True, text=True, timeout=timeout,
            )
        else:
            args.append(prompt)
            result = subprocess.run(
                args, capture_output=True, text=True, timeout=timeout,
            )
        if result.returncode != 0:
            err = result.stderr.strip() or "unknown error"
            raise RuntimeError(f"{self.name} failed: {err}")
        return result.stdout.strip()
