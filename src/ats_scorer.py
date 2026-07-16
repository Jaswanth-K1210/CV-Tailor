import re
from collections import Counter

from src.sanitizer import STOPWORDS, has_dashes

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE = re.compile(r"\b\d{3}[\s.]?\d{3}[\s.]?\d{4}\b")
_SECTIONS = ("summary", "experience", "skill", "education")


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z][a-zA-Z+#.]*[a-zA-Z]|[a-zA-Z]", text.lower())


def extract_keywords(jd: str, top_n: int = 30) -> list[str]:
    counts = Counter(
        t for t in _tokens(jd)
        if t not in STOPWORDS and len(t) > 2
    )
    return [w for w, _ in counts.most_common(top_n)]


def score_cv(cv: str, jd: str) -> dict:
    keywords = extract_keywords(jd)
    cv_tokens = set(_tokens(cv))
    notes: list[str] = []

    present = [k for k in keywords if k in cv_tokens]
    missing = [k for k in keywords if k not in cv_tokens]
    coverage = (len(present) / len(keywords)) if keywords else 1.0
    score = coverage * 60.0

    cv_lower = cv.lower()
    for section in _SECTIONS:
        if section in cv_lower:
            score += 4.0
        else:
            notes.append(f"missing section: {section}")

    if _EMAIL.search(cv) or _PHONE.search(cv):
        score += 8.0
    else:
        notes.append("no contact info found")

    word_count = len(cv.split())
    if 150 <= word_count <= 1200:
        score += 8.0
    else:
        notes.append(f"length {word_count} words is outside 150 to 1200")

    if re.search(r"\d", cv):
        score += 8.0
    else:
        notes.append("no quantified achievements (numbers) found")

    if has_dashes(cv):
        score -= 10.0
        notes.append("contains dashes")

    final = max(0, min(100, round(score)))
    if missing:
        notes.append("missing keywords: " + ", ".join(missing[:10]))
    return {"score": final, "missing_keywords": missing, "notes": notes}
