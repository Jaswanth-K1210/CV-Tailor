import pytest

from src.generator import build_prompt, generate_cv, EngineError


def test_build_prompt_includes_all_rules_and_inputs():
    p = build_prompt("MY CV", "THE JD", feedback="make it punchier",
                     previous_draft="OLD DRAFT", missing_keywords=["kubernetes", "aws"])
    assert "THE JD" in p
    assert "OLD DRAFT" in p
    assert "kubernetes" in p and "aws" in p
    low = p.lower()
    assert "no dash" in low or "dashes" in low
    assert "keyword" in low


def test_build_prompt_initial_includes_source_cv():
    p = build_prompt("MY CV", "THE JD", feedback="make it punchier")
    assert "MY CV" in p
    assert "THE JD" in p
    assert "make it punchier" in p


def test_build_prompt_minimal_no_optional_sections():
    p = build_prompt("CV", "JD")
    assert "CV" in p and "JD" in p


_FAKE_SETTINGS = {"engine": "claude", "model": "sonnet", "budget_usd": 0.10}


class _FakeSettings:
    @staticmethod
    def load():
        return dict(_FAKE_SETTINGS)


def test_generate_cv_returns_engine_output(monkeypatch):
    class FakeEngine:
        def generate(self, prompt, model, timeout=120):
            return "Generated CV text"

    monkeypatch.setattr("src.generator.get_engine", lambda name: FakeEngine())
    monkeypatch.setattr("src.generator.settings", _FakeSettings())
    assert generate_cv("CV", "JD") == "Generated CV text"


def test_generate_cv_raises_on_engine_error(monkeypatch):
    class FakeEngine:
        def generate(self, prompt, model, timeout=120):
            raise RuntimeError("not logged in")

    monkeypatch.setattr("src.generator.get_engine", lambda name: FakeEngine())
    monkeypatch.setattr("src.generator.settings", _FakeSettings())
    with pytest.raises(EngineError):
        generate_cv("CV", "JD")


def test_generate_cv_uses_timeout_from_settings(monkeypatch):
    captured = {}

    class FakeEngine:
        def generate(self, prompt, model, timeout=300):
            captured["timeout"] = timeout
            return "CV"

    class TimeoutSettings:
        @staticmethod
        def load():
            return {"engine": "claude", "model": "sonnet", "timeout_seconds": 420}

    monkeypatch.setattr("src.generator.get_engine", lambda name: FakeEngine())
    monkeypatch.setattr("src.generator.settings", TimeoutSettings())
    generate_cv("CV", "JD")
    assert captured["timeout"] == 420


def test_generate_cv_explicit_timeout_overrides_settings(monkeypatch):
    captured = {}

    class FakeEngine:
        def generate(self, prompt, model, timeout=300):
            captured["timeout"] = timeout
            return "CV"

    monkeypatch.setattr("src.generator.get_engine", lambda name: FakeEngine())
    monkeypatch.setattr("src.generator.settings", _FakeSettings())
    generate_cv("CV", "JD", timeout=99)
    assert captured["timeout"] == 99


def test_generate_cv_raises_when_engine_missing(monkeypatch):
    def boom(name):
        raise ValueError("Unknown engine: nope")

    monkeypatch.setattr("src.generator.get_engine", boom)
    monkeypatch.setattr("src.generator.settings", _FakeSettings())
    with pytest.raises(EngineError):
        generate_cv("CV", "JD")
