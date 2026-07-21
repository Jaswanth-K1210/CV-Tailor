from __future__ import annotations

import os
import platform
import shutil
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
    def _generate_args(self, model: str, budget_usd: float) -> list[str]:
        """Return CLI args for headless generation (prompt goes via stdin)."""

    def find_binary(self) -> str | None:
        system = platform.system()
        for name in self._binary_names():
            path = shutil.which(name)
            if path:
                return path
        for path in self._search_paths():
            candidates = [path]
            if system == "Windows":
                candidates.append(path + ".exe")
            for candidate in candidates:
                if os.path.isfile(candidate):
                    return candidate
        return None

    def check(self) -> dict:
        binary = self.find_binary()
        if not binary:
            return {"ok": False, "error": f"{self.name} CLI not found"}
        try:
            import subprocess
            r = subprocess.run(
                [binary] + self._version_args(),
                capture_output=True, text=True, timeout=15,
            )
            version = r.stdout.strip() or r.stderr.strip()
            return {"ok": r.returncode == 0, "version": version}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def generate(self, prompt: str, model: str, budget_usd: float,
                 timeout: int = 120) -> str:
        import subprocess
        binary = self.find_binary()
        if not binary:
            raise RuntimeError(f"{self.name} CLI not found")
        args = [binary] + self._generate_args(model, budget_usd)
        result = subprocess.run(
            args, input=prompt, capture_output=True, text=True, timeout=timeout,
        )
        if result.returncode != 0:
            err = result.stderr.strip() or "unknown error"
            raise RuntimeError(f"{self.name} failed: {err}")
        return result.stdout.strip()
