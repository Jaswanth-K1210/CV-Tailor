from __future__ import annotations

import logging
import subprocess

from src.engines import get_engine, ENGINE_LABELS, DEFAULT_MODELS
import src.settings as settings

logger = logging.getLogger(__name__)


class EngineError(Exception):
    pass


_RULES = """Rewrite the CV below to match this job description. You will be scored by an ATS.

SCORING CRITERIA (maximize each):
1. KEYWORDS (35 pts): Naturally weave in top skills/terms from the JD. Aim for 25+ matches.
2. SECTIONS (20 pts): Use these exact headers: Education, Experience, Skills, Projects. Add Summary only if 5+ years experience.
3. CONTACT (10 pts): Include email, phone, LinkedIn, GitHub on the contact line.
4. LENGTH (10 pts): 200-500 words. One page only.
5. QUANTIFIED ACHIEVEMENTS (10 pts): Include 5+ numbers (%, $, K/M/B, user counts).
6. ACTION VERBS (7 pts): Start every bullet with a strong verb (Built, Designed, Led, Optimized, etc.).
7. BULLET POINTS (5 pts): Use 5+ bullets with the bullet character.

FORMATTING:
- ONE PAGE: under 450 words. No dashes (use "to" not "-").
- Section order: Name, Contact, Education, Experience, Projects, Technical Skills.
- Contact line format: Name | phone | email | linkedin | github
- 2-space indent before bullets. Separate title and date with 2+ spaces.
- No "I/my/me/myself" anywhere.
- Technical Skills: 2-space indent, "Category:" then comma-separated skills.
- Return ONLY the finished CV text. No preamble, no markdown, no commentary."""


_RETRY_RULES = """You are refining a CV draft to improve its ATS score. Focus SPECIFICALLY on:

1. ADD THESE MISSING KEYWORDS naturally: {keywords}
2. Keep all existing good content, only adjust to incorporate missing terms.
3. Maintain the same formatting rules as before.

FORMATTING:
- ONE PAGE: under 450 words. No dashes (use "to" not "-").
- Section order: Name, Contact, Education, Experience, Projects, Technical Skills.
- Contact line format: Name | phone | email | linkedin | github
- 2-space indent before bullets. Separate title and date with 2+ spaces.
- Start every bullet with an action verb. Quantify results. No "I/my/me".
- 5+ bullet points with the bullet character. 5+ quantified achievements.
- Technical Skills: 2-space indent, "Category:" then comma-separated skills.
- Return ONLY the finished CV text. No preamble, no markdown, no commentary."""


def build_prompt(source_cv: str, jd: str, feedback: str = "",
                 previous_draft: str = "", missing_keywords=None) -> str:
    if previous_draft and missing_keywords:
        prompt = _RETRY_RULES.format(keywords=", ".join(missing_keywords))
        parts = [prompt, "\n\nJOB DESCRIPTION:\n", jd, "\n\nCV TO IMPROVE:\n", previous_draft]
    else:
        parts = [_RULES, "\n\nJOB DESCRIPTION:\n", jd, "\n\nSOURCE CV:\n", source_cv]
        if missing_keywords:
            parts += ["\n\nADD THESE KEYWORDS: ", ", ".join(missing_keywords)]
        if feedback:
            parts += ["\n\nFEEDBACK: ", feedback]
    return "".join(parts)


def generate_cv(source_cv: str, jd: str, feedback: str = "",
                previous_draft: str = "", missing_keywords=None,
                timeout: int | None = None) -> str:
    prompt = build_prompt(source_cv, jd, feedback, previous_draft, missing_keywords)
    logger.debug("prompt length: %d chars", len(prompt))
    cfg = settings.load()
    engine_name = cfg.get("engine", "claude")
    model = cfg.get("model", DEFAULT_MODELS.get(engine_name, "sonnet"))
    if timeout is None:
        timeout = int(cfg.get("timeout_seconds", 300))
    logger.info("engine=%s  model=%s  timeout=%ds", engine_name, model, timeout)
    try:
        engine = get_engine(engine_name)
    except ValueError as exc:
        raise EngineError(str(exc)) from exc
    try:
        return engine.generate(prompt, model, timeout=timeout)
    except FileNotFoundError as exc:
        raise EngineError(
            f"{ENGINE_LABELS.get(engine_name, engine_name)} CLI not found. "
            f"Install it and log in, then try again."
        ) from exc
    except RuntimeError as exc:
        raise EngineError(str(exc)) from exc
    except subprocess.TimeoutExpired as exc:
        raise EngineError(
            f"generation timed out after {timeout}s. The job description may be "
            f"very long or the model is slow. Try a shorter JD, a faster model, "
            f"or raise \"timeout_seconds\" in ~/.cv-tailor/settings.json."
        ) from exc
