import subprocess


class EngineError(Exception):
    pass


_RULES = """You are an expert resume writer. Rewrite the candidate's CV so it is
tightly tailored to the target job. Follow these rules strictly:
1. Write in natural, humanized language that reads like a real person wrote it.
   Avoid robotic or obvious AI phrasing.
2. Do not use dash: no hyphen, no en dash, no em dash. Rephrase anything
   that would need one.
3. Optimize for ATS: naturally include the important keywords and skills from
   the job description so an applicant tracking system scores it highly.
4. Do not robotically repeat the same words. Vary verbs and phrasing, while
   still keeping the essential job description keywords.
5. Keep it truthful to the candidate's real experience. Do not invent employers
   or degrees. You may rephrase and re prioritize.
6. Use clear sections: Summary, Experience, Skills, Education, and contact info.
7. Return only the finished CV text, no preamble or commentary."""


def build_prompt(source_cv: str, jd: str, feedback: str = "",
                 previous_draft: str = "", missing_keywords=None) -> str:
    parts = [_RULES, "\n=== TARGET JOB DESCRIPTION ===\n", jd,
             "\n=== CANDIDATE CURRENT CV ===\n", source_cv]
    if previous_draft:
        parts += ["\n=== PREVIOUS DRAFT (improve on this) ===\n", previous_draft]
    if missing_keywords:
        parts += ["\n=== KEYWORDS TO WORK IN NATURALLY ===\n",
                  ", ".join(missing_keywords)]
    if feedback:
        parts += ["\n=== USER FEEDBACK TO APPLY ===\n", feedback]
    parts += ["\n\nReturn only the finished CV text."]
    return "".join(parts)


def generate_cv(source_cv: str, jd: str, feedback: str = "",
                previous_draft: str = "", missing_keywords=None,
                timeout: int = 180) -> str:
    prompt = build_prompt(source_cv, jd, feedback, previous_draft, missing_keywords)
    try:
        result = subprocess.run(
            ["claude", "-p"],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        raise EngineError(
            "claude CLI not found. Install Claude Code and run `claude` to log in."
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise EngineError("generation timed out; try again") from exc
    if result.returncode != 0:
        raise EngineError(
            f"claude failed: {result.stderr.strip() or 'unknown error'}"
        )
    return result.stdout.strip()
