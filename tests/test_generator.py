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
    assert "jd keywords" in low
    assert "repeat" in low


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
        def generate(self, prompt, model, budget, timeout=120):
            return "Generated CV text"

    monkeypatch.setattr("src.generator.get_engine", lambda name: FakeEngine())
    monkeypatch.setattr("src.generator.settings", _FakeSettings())
    assert generate_cv("CV", "JD") == "Generated CV text"


def test_generate_cv_raises_on_engine_error(monkeypatch):
    class FakeEngine:
        def generate(self, prompt, model, budget, timeout=120):
            raise RuntimeError("not logged in")

    monkeypatch.setattr("src.generator.get_engine", lambda name: FakeEngine())
    monkeypatch.setattr("src.generator.settings", _FakeSettings())
    with pytest.raises(EngineError):
        generate_cv("CV", "JD")


def test_generate_cv_raises_when_engine_missing(monkeypatch):
    def boom(name):
        raise ValueError("Unknown engine: nope")

    monkeypatch.setattr("src.generator.get_engine", boom)
    monkeypatch.setattr("src.generator.settings", _FakeSettings())
    with pytest.raises(EngineError):
        generate_cv("CV", "JD")
