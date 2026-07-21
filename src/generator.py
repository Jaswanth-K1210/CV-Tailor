import os
import shutil
import subprocess

from src.engines import get_engine, ENGINE_LABELS, DEFAULT_MODELS
import src.settings as settings


class EngineError(Exception):
    pass


_RULES = """Rewrite the CV below to match this job. STRICT RULES:
- ONE PAGE ONLY: under 450 words. No dashes (use "to" not "-").
- Sections in order: Name, Contact, Education, Experience, Projects, Technical Skills. Add Summary only if 5+ years experience.
- Contact line: Name | phone | email | linkedin | github
- Use 2 spaces indent before bullets. Separate title and date with 2+ spaces.
- Start every bullet with an action verb. Quantify results. No "I/my/me".
- Naturally include JD keywords. Vary phrasing, no robotic repetition.
- Technical Skills: 2-space indent, "Category:" label then comma-separated skills.
- Return ONLY the finished CV text. No preamble, no markdown, no commentary."""


def build_prompt(source_cv: str, jd: str, feedback: str = "",
                 previous_draft: str = "", missing_keywords=None) -> str:
    parts = [_RULES, "\n\nJOB:\n", jd, "\n\nCV:\n", source_cv]
    if previous_draft:
        parts += ["\n\nPREVIOUS DRAFT (improve, don't repeat full text):\n", previous_draft]
    if missing_keywords:
        parts += ["\n\nADD THESE KEYWORDS: ", ", ".join(missing_keywords)]
    if feedback:
        parts += ["\n\nFEEDBACK: ", feedback]
    return "".join(parts)


def generate_cv(source_cv: str, jd: str, feedback: str = "",
                previous_draft: str = "", missing_keywords=None,
                timeout: int = 120) -> str:
    prompt = build_prompt(source_cv, jd, feedback, previous_draft, missing_keywords)
    cfg = settings.load()
    engine_name = cfg.get("engine", "claude")
    model = cfg.get("model", DEFAULT_MODELS.get(engine_name, "sonnet"))
    budget = cfg.get("budget_usd", 0.10)
    try:
        engine = get_engine(engine_name)
    except ValueError as exc:
        raise EngineError(str(exc)) from exc
    try:
        return engine.generate(prompt, model, budget, timeout=timeout)
    except FileNotFoundError as exc:
        raise EngineError(
            f"{ENGINE_LABELS.get(engine_name, engine_name)} CLI not found. "
            f"Install it and log in, then try again."
        ) from exc
    except RuntimeError as exc:
        raise EngineError(str(exc)) from exc
    except subprocess.TimeoutExpired as exc:
        raise EngineError("generation timed out; try again") from exc
