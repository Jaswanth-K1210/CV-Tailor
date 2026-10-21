from __future__ import annotations

import re

from src.generator import _RULES
from src.llm import ask_json
from src.profile import dumps

_FORMAT = "FORMATTING:" + _RULES.split("FORMATTING:", 1)[1]

_WRITE_PROMPT = """Write a one-page resume (Jake's resume template) tailored to the job below,
using ONLY facts from the PROFILE. Pick the most relevant experience and projects,
reorder, trim and reword them to match the job's keywords.
Never invent a project, employer, metric, date or skill that is not in the PROFILE.
If a number is not in the PROFILE, describe the impact without one.

{fmt}
{feedback}
JOB DESCRIPTION:
{jd}

PROFILE (JSON):
{profile}
{previous}"""

_REVIEW_PROMPT = """You are a strict, honest hiring manager reviewing a resume for the job below.
Score it 0-10 for how strongly it would get this candidate an interview.
Check every claim against the PROFILE; anything not backed by it is a fabrication.
List job requirements the PROFILE has no evidence for as missing_from_profile,
phrased as a short question to the candidate (e.g. "Have you used Kubernetes? Where?").

Return ONLY JSON: {{"score": number, "issues": [str], "fabrications": [str],
"missing_from_profile": [str]}}

ATS CHECK RESULT: score {ats_score}/100. Issues: {ats_issues}

JOB DESCRIPTION:
{jd}

PROFILE (JSON):
{profile}

RESUME:
{resume}"""


def write_resume(profile: dict, jd: str, llm, feedback: str = "",
                 previous: str = "") -> str:
    return llm(_WRITE_PROMPT.format(
        fmt=_FORMAT, jd=jd, profile=dumps(profile),
        feedback=f"\nFIX THESE PROBLEMS FROM THE LAST DRAFT:\n{feedback}\n" if feedback else "",
        previous=f"\nLAST DRAFT:\n{previous}" if previous else "",
    )).strip()


def _score(raw) -> float:
    m = re.search(r"\d+(?:\.\d+)?", str(raw))
    return float(m.group()) if m else 0.0


def review_resume(profile: dict, jd: str, resume: str, ats: dict, llm) -> dict:
    r = ask_json(llm, _REVIEW_PROMPT.format(
        ats_score=ats.get("score", "?"), ats_issues="; ".join(ats.get("issues", [])) or "none",
        jd=jd, profile=dumps(profile), resume=resume,
    ), "review")
    return {
        "score": _score(r.get("score")),
        "issues": list(r.get("issues") or []),
        "fabrications": list(r.get("fabrications") or []),
        "missing_from_profile": list(r.get("missing_from_profile") or []),
    }
