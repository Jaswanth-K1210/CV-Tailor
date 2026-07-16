import subprocess

import pytest

from src.generator import build_prompt, generate_cv, EngineError


def test_build_prompt_includes_all_rules_and_inputs():
    p = build_prompt("MY CV", "THE JD", feedback="make it punchier",
                     previous_draft="OLD DRAFT", missing_keywords=["kubernetes", "aws"])
    assert "MY CV" in p
    assert "THE JD" in p
    assert "make it punchier" in p
    assert "OLD DRAFT" in p
    assert "kubernetes" in p and "aws" in p
    low = p.lower()
    assert "no dash" in low or "do not use dash" in low
    assert "ats" in low
    assert "repeat" in low


def test_build_prompt_minimal_no_optional_sections():
    p = build_prompt("CV", "JD")
    assert "CV" in p and "JD" in p


def test_generate_cv_returns_stripped_stdout(monkeypatch):
    class FakeCompleted:
        returncode = 0
        stdout = "  Generated CV text  "
        stderr = ""

    monkeypatch.setattr(subprocess, "run", lambda *a, **k: FakeCompleted())
    assert generate_cv("CV", "JD") == "Generated CV text"


def test_generate_cv_raises_on_nonzero_exit(monkeypatch):
    class FakeCompleted:
        returncode = 1
        stdout = ""
        stderr = "not logged in"

    monkeypatch.setattr(subprocess, "run", lambda *a, **k: FakeCompleted())
    with pytest.raises(EngineError):
        generate_cv("CV", "JD")


def test_generate_cv_raises_when_claude_missing(monkeypatch):
    def boom(*a, **k):
        raise FileNotFoundError()

    monkeypatch.setattr(subprocess, "run", boom)
    with pytest.raises(EngineError):
        generate_cv("CV", "JD")
