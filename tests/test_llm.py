import pytest

from src.llm import ask_json, parse_json


def _fake(outputs):
    seen = []

    def llm(prompt):
        seen.append(prompt)
        return outputs[len(seen) - 1]
    llm.seen = seen
    return llm


def test_parse_json_fenced():
    assert parse_json('```json\n{"a": 1}\n```') == {"a": 1}


def test_parse_json_with_prose():
    assert parse_json('Sure! Here it is: {"a": {"b": 2}} Hope that helps.') == {"a": {"b": 2}}


def test_parse_json_raises_on_garbage():
    with pytest.raises(ValueError):
        parse_json("no json here")


def test_ask_json_retries_once_then_succeeds():
    llm = _fake(["oops", '{"ok": true}'])
    assert ask_json(llm, "P", "review") == {"ok": True}
    assert "Return ONLY valid JSON." in llm.seen[1]


def test_ask_json_raises_after_two_failures():
    llm = _fake(["oops", "still oops"])
    with pytest.raises(ValueError, match="review: model did not return valid JSON"):
        ask_json(llm, "P", "review")
