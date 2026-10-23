from __future__ import annotations

import json
import re

from src.llm import ask_json
from src.profile import dumps
from src.sanitizer import remove_dashes

_WRITE_PROMPT = """Write a one-page resume in Jake's resume template, tailored to the job below,
using ONLY facts from the PROFILE. Pick the most relevant experience and projects,
reorder, trim and reword them to match the job's keywords.
Never invent a project, employer, metric, date, link or skill that is not in the PROFILE.
If a number is not in the PROFILE, describe the impact without one.
Use a job keyword only where the PROFILE backs it; no self-assessment sentences
("meets the requirements") and no keyword stuffing.

RULES:
- One page: 2 to 4 experience entries, 2 to 4 projects, 2 to 4 bullets each, about 400 words total.
- Every bullet starts with a strong action verb, has no "I/my/me", and shows impact.
- Dates like "May 2024 to Jul 2025" or "Present". No dashes or hyphens in text.
- Copy contact links (email, phone, linkedin, github, website) and project links exactly
  from the PROFILE; leave a field empty if the PROFILE doesn't have it.
- Skills: 3 to 5 categories, only skills in the PROFILE, most relevant to the job first.
{feedback}
Return ONLY JSON in this shape:
{{"name": str,
  "contact": {{"phone": str, "email": str, "linkedin": str, "github": str, "website": str, "location": str}},
  "education": [{{"school": str, "location": str, "degree": str, "dates": str, "details": [str]}}],
  "experience": [{{"title": str, "company": str, "location": str, "dates": str, "bullets": [str]}}],
  "projects": [{{"name": str, "tech": [str], "link": str, "dates": str, "bullets": [str]}}],
  "skills": [{{"category": str, "items": [str]}}]}}

JOB DESCRIPTION:
{jd}

PROFILE (JSON):
{profile}
{previous}"""

_REVIEW_PROMPT = """You are a strict, honest hiring manager reviewing a resume for the job below.
Give two scores, 0 to 10:
- "score": how good THIS RESUME is as a presentation of THIS candidate's real PROFILE for
  this job. 10 means no better resume could be written from this PROFILE without inventing
  anything. Judge selection of the most relevant items, keyword use, bullet impact, clarity
  and one-page fit. Do NOT lower it for experience the PROFILE lacks.
- "fit": how well the candidate's real experience matches the job (missing experience lowers this).
"issues" are concrete fixes the writer can make from the PROFILE alone.
Check every claim against the PROFILE. "fabrications" lists ONLY claims the PROFILE
does not support (empty list if none); never list supported items or notes there.
List job requirements the PROFILE has no evidence for as missing_from_profile,
phrased as a short question to the candidate (e.g. "Have you used Kubernetes? Where?").
Never ask about anything already covered in PROFILE.user_answers, even reworded.

Return ONLY JSON: {{"score": number, "fit": number, "issues": [str], "fabrications": [str],
"missing_from_profile": [str]}}

ATS CHECK RESULT: score {ats_score}/100. Issues: {ats_issues}

JOB DESCRIPTION:
{jd}

PROFILE (JSON):
{profile}

RESUME:
{resume}"""

# Fields that hold links or contact details; everything else is prose and gets the no-dash rule.
_KEEP_AS_IS = {"phone", "email", "linkedin", "github", "website", "link"}


def _clean(value, key: str = ""):
    if isinstance(value, dict):
        return {k: _clean(v, k) for k, v in value.items()}
    if isinstance(value, list):
        return [_clean(v, key) for v in value]
    if isinstance(value, str):
        return value.strip() if key in _KEEP_AS_IS else remove_dashes(value).strip()
    return value


def write_resume(profile: dict, jd: str, llm, feedback: str = "",
                 previous: dict | None = None) -> dict:
    r = ask_json(llm, _WRITE_PROMPT.format(
        jd=jd, profile=dumps(profile),
        feedback=f"\nFIX THESE PROBLEMS FROM THE LAST DRAFT:\n{feedback}\n" if feedback else "",
        previous=f"\nLAST DRAFT (JSON):\n{json.dumps(previous, ensure_ascii=False)}" if previous else "",
    ), "write")
    r = _clean(r)
    r.setdefault("name", (profile.get("contact") or {}).get("name", ""))
    r.setdefault("contact", {})
    for key in ("education", "experience", "projects", "skills"):
        r[key] = [x for x in (r.get(key) or []) if isinstance(x, dict)]
    return r


def resume_to_text(resume: dict) -> str:
    """Plain text of the resume, in reading order, for ATS scoring and review."""
    c = resume.get("contact") or {}
    lines = [resume.get("name", ""),
             " | ".join(v for v in (c.get(k) for k in ("phone", "email", "linkedin",
                                                         "github", "website", "location")) if v)]

    def section(title, items, head):
        if items:
            lines.extend(["", title.upper()])
            for it in items:
                lines.append(head(it))
                lines.extend(f"  • {b}" for b in it.get("bullets") or it.get("details") or [])

    section("Education", resume.get("education"),
            lambda e: f"{e.get('school', '')}  {e.get('dates', '')}\n{e.get('degree', '')}  {e.get('location', '')}")
    section("Experience", resume.get("experience"),
            lambda e: f"{e.get('title', '')}  {e.get('dates', '')}\n{e.get('company', '')}  {e.get('location', '')}")
    section("Projects", resume.get("projects"),
            lambda p: f"{p.get('name', '')} | {', '.join(p.get('tech') or [])}  {p.get('dates', '')}")
    if resume.get("skills"):
        lines.extend(["", "TECHNICAL SKILLS"])
        lines.extend(f"{s.get('category', '')}: {', '.join(s.get('items') or [])}"
                     for s in resume["skills"])
    return "\n".join(lines).strip()


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
        "fit": _score(r.get("fit")),
        "issues": list(r.get("issues") or []),
        "fabrications": list(r.get("fabrications") or []),
        "missing_from_profile": list(r.get("missing_from_profile") or []),
    }
