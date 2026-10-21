import pytest

from src.engines import (
    ENGINE_MAP,
    DEFAULT_MODELS,
    ENGINE_LABELS,
    get_engine,
)


def test_ollama_is_registered():
    assert "ollama" in ENGINE_MAP
    assert "ollama" in ENGINE_LABELS
    assert "ollama" in DEFAULT_MODELS
    eng = get_engine("ollama")
    assert eng.name == "ollama"


def test_ollama_uses_stdin_and_run():
    eng = get_engine("ollama")
    assert eng._send_prompt_via_stdin() is True
    assert eng._generate_args("llama3.2") == ["run", "llama3.2"]


def test_gemini_prompt_flag_is_last_so_prompt_becomes_its_value():
    # `gemini -m <model> -p <prompt>`: -p must come last because the prompt is
    # appended after these args. If -m/model followed -p, gemini errors with
    # "Not enough arguments following: p".
    eng = get_engine("gemini")
    args = eng._generate_args("gemini-2.5-flash")
    assert args[-1] == "-p"
    assert args == ["-m", "gemini-2.5-flash", "-p"]
    assert eng._send_prompt_via_stdin() is False


def test_opencode_default_model_is_available_zen_model():
    # Default must be a model that works without extra credentials.
    assert DEFAULT_MODELS["opencode"].startswith("opencode/")


class _FakeCompleted:
    def __init__(self, stdout="", stderr="", returncode=0):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


def test_generate_strips_ansi_escape_codes(monkeypatch):
    eng = get_engine("opencode")
    monkeypatch.setattr(eng, "find_binary", lambda: "/usr/local/bin/opencode")
    captured = {}

    def fake_run(args, **kwargs):
        captured["cwd"] = kwargs.get("cwd")
        return _FakeCompleted(stdout="\x1b[0m\x1b[1mHello CV\x1b[0m\n")

    monkeypatch.setattr("src.engines.base.subprocess.run", fake_run)
    out = eng.generate("prompt", "opencode/deepseek-v4-flash-free", timeout=10)
    assert out == "Hello CV"
    # runs in an isolated temp working directory, not the project dir
    assert captured["cwd"] is not None
    assert "cv-tailor-" in captured["cwd"]


def test_generate_raises_runtimeerror_on_nonzero_exit(monkeypatch):
    eng = get_engine("claude")
    monkeypatch.setattr(eng, "find_binary", lambda: "/usr/local/bin/claude")
    monkeypatch.setattr(
        "src.engines.base.subprocess.run",
        lambda args, **kw: _FakeCompleted(stderr="not logged in", returncode=1),
    )
    with pytest.raises(RuntimeError):
        eng.generate("prompt", "sonnet", timeout=10)


def test_agy_engine_args():
    from src.engines import get_engine
    eng = get_engine("agy")
    assert eng._binary_names() == ["agy"]
    assert eng._generate_args("m") == ["--model", "m", "-p"]
    assert eng._send_prompt_via_stdin() is False
