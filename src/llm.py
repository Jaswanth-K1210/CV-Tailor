from __future__ import annotations

import json
import re
from typing import Callable

from src.engines import DEFAULT_MODELS, get_engine

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.S)


def parse_json(text: str) -> dict:
    m = _FENCE_RE.search(text)
    candidate = m.group(1) if m else text[text.find("{"):text.rfind("}") + 1]
    try:
        obj = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON: {exc}") from exc
    if not isinstance(obj, dict):
        raise ValueError("expected a JSON object")
    return obj


def make_llm(engine: str, model: str | None = None,
             timeout: int = 300) -> Callable[[str], str]:
    eng = get_engine(engine)
    model = model or DEFAULT_MODELS[engine]
    return lambda prompt: eng.generate(prompt, model, timeout=timeout)


def ask_json(llm: Callable[[str], str], prompt: str, step: str) -> dict:
    try:
        return parse_json(llm(prompt))
    except ValueError:
        pass
    try:
        return parse_json(llm(prompt + "\n\nReturn ONLY valid JSON."))
    except ValueError as exc:
        raise ValueError(f"{step}: model did not return valid JSON") from exc
