from __future__ import annotations

import json
import zipfile

import requests

from src.llm import ask_json

AI_PASTE_PROMPT = (
    "List every project, job, internship, achievement, certification and skill "
    "you know about me. For each: name, what it does, my role, tech used, "
    "measurable results, dates, links. Don't invent anything; say 'unknown' "
    "where you don't know."
)

_LIST_KEYS = ("education", "experience", "projects", "achievements", "certifications")

_MERGE_PROMPT = """Merge the sources below into one master profile of this person.
Keep EVERY project, job, achievement and skill mentioned in any source; merge duplicates.
Never invent anything that is not in the sources.
Return ONLY a JSON object with keys:
contact {{name, email, phone, linkedin, github, location}},
education [{{school, degree, dates, gpa, details, source}}],
experience [{{company, title, dates, location, bullets[], tech[], source}}],
projects [{{name, description, bullets[], tech[], link, dates, source}}],
skills {{category: [skill]}},
achievements [{{text, source}}],
certifications [{{name, issuer, date, source}}].
"source" is the name of the source the item came from ({names}).

{sources}"""


def github_text(username: str) -> str:
    r = requests.get(f"https://api.github.com/users/{username}/repos",
                     params={"per_page": 100, "sort": "updated"}, timeout=20)
    r.raise_for_status()
    return "\n".join(
        f"{repo['name']}: {repo.get('description') or ''} "
        f"[{repo.get('language') or ''}] {repo['html_url']}"
        for repo in r.json() if not repo.get("fork")
    )


def linkedin_text(zip_path: str) -> str:
    parts = []
    with zipfile.ZipFile(zip_path) as zf:
        names = {n.rsplit("/", 1)[-1]: n for n in zf.namelist()}
        for wanted in ("Positions.csv", "Education.csv", "Skills.csv", "Projects.csv"):
            if wanted in names:
                text = zf.read(names[wanted]).decode("utf-8", errors="replace")
                parts.append(f"## {wanted}\n{text}")
    return "\n\n".join(parts)


def build_profile(sources: dict[str, str], llm) -> dict:
    body = "\n\n".join(f"=== SOURCE: {k} ===\n{v}" for k, v in sources.items() if v)
    prompt = _MERGE_PROMPT.format(names=", ".join(sources), sources=body)
    p = ask_json(llm, prompt, "profile")
    p.setdefault("contact", {})
    p.setdefault("skills", {})
    for key in _LIST_KEYS:
        p.setdefault(key, [])
        for item in p[key]:
            if isinstance(item, dict):
                item.setdefault("source", "unknown")
    return p


def dumps(p: dict) -> str:
    return json.dumps(p, indent=2, ensure_ascii=False)
