import re
import logging
from collections import Counter

from src.sanitizer import STOPWORDS, has_dashes

logger = logging.getLogger(__name__)

_DASH_CLASS = "[\\-\u2013\u2014]"

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE = re.compile(r"\b\d{3}[\s.\-]?\d{3}[\s.\-]?\d{4}\b")
_LINKEDIN = re.compile(r"linkedin\.com/in/[\w\-]+", re.I)
_GITHUB = re.compile(r"github\.com/[\w\-]+", re.I)

_STANDARD_SECTIONS = {
    "education": (["education", "academic"], 4.0),
    "experience": (["experience", "work experience", "employment", "work history"], 4.0),
    "skills": (["skills", "technical skills", "technical proficiency", "competencies"], 4.0),
    "projects": (["projects", "portfolio", "key projects"], 3.0),
    "summary": (["summary", "objective", "profile", "about"], 2.0),
    "certifications": (["certifications", "certificates", "licenses", "achievements",
                        "achievements & certifications", "awards"], 2.0),
}

_ACTION_VERBS = {
    "built", "designed", "developed", "implemented", "engineered", "created",
    "led", "managed", "directed", "established", "founded", "launched",
    "improved", "optimized", "enhanced", "reduced", "increased", "automated",
    "streamlined", "accelerated", "scaled", "migrated", "refactored",
    "delivered", "shipped", "deployed", "released", "launched",
    "analyzed", "evaluated", "investigated", "researched", "identified",
    "collaborated", "mentored", "coordinated", "facilitated", "presented",
    "configured", "integrated", "maintained", "troubleshot", "debugged",
    "authored", "documented", "architected", "conceptualized", "spearheaded",
    "orchestrated", "pioneered", "championed", "drove", "owned",
}


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z][a-zA-Z+#.]*[a-zA-Z]|[a-zA-Z]", text.lower())


def extract_keywords(jd: str, top_n: int = 30) -> list[str]:
    counts = Counter(
        t for t in _tokens(jd)
        if t not in STOPWORDS and len(t) > 2
    )
    return [w for w, _ in counts.most_common(top_n)]


def _count_exact_keywords(cv_tokens: set[str], keywords: list[str]) -> tuple[int, list[str]]:
    present = [k for k in keywords if k in cv_tokens]
    missing = [k for k in keywords if k not in cv_tokens]
    return len(present), missing


def _count_partial_matches(cv_lower: str, keywords: list[str]) -> int:
    count = 0
    for kw in keywords:
        if len(kw) > 4 and kw not in cv_lower:
            base = kw[:max(len(kw)//2, 3)]
            if base in cv_lower:
                count += 1
        elif len(kw) <= 4 and kw not in cv_lower:
            if kw in cv_lower:
                count += 1
    return count


def _has_action_verbs(cv_text: str) -> bool:
    words = set(cv_text.lower().split())
    return bool(words & _ACTION_VERBS)


def _count_quantified(cv_text: str) -> int:
    patterns = [
        r"\d+%", r"\d+\+?", r"\$\d+", r"\d{1,3}(?:,\d{3})+",
        r"\d+\s*(?:K|M|B|k|m|b)\+?",
        r"\b(?:50|100|200|500|1000|10K|50K|100K|1M)\b",
    ]
    count = 0
    for pat in patterns:
        count += len(re.findall(pat, cv_text))
    return count


def _check_sections(cv_lower: str) -> tuple[float, list[str]]:
    score = 0.0
    notes = []
    for section_name, (aliases, pts) in _STANDARD_SECTIONS.items():
        found = any(alias in cv_lower for alias in aliases)
        if found:
            score += pts
        else:
            notes.append(f"missing section: {section_name}")
    return score, notes


def _check_contact(cv_text: str) -> tuple[float, list[str]]:
    score = 0.0
    notes = []
    if _EMAIL.search(cv_text):
        score += 3.0
    else:
        notes.append("no email found")
    if _PHONE.search(cv_text):
        score += 2.0
    else:
        notes.append("no phone found")
    if _LINKEDIN.search(cv_text) or "linkedin" in cv_text.lower():
        score += 2.0
    else:
        notes.append("no LinkedIn found")
    if _GITHUB.search(cv_text) or "github" in cv_text.lower():
        score += 1.0
    return score, notes


def _check_length(cv_text: str) -> tuple[float, list[str]]:
    word_count = len(cv_text.split())
    notes = []
    if word_count < 80:
        return 0.0, [f"too short: {word_count} words (need 100+)"]
    if word_count > 600:
        return 0.0, [f"too long: {word_count} words (need <600 for 1 page)"]
    if 200 <= word_count <= 500:
        return 10.0, []
    if 150 <= word_count < 200:
        return 8.0, []
    if 100 <= word_count < 150:
        return 6.0, [f"on the short side: {word_count} words"]
    return 4.0, [f"{word_count} words (aim for 150-500)"]


def score_cv(cv: str, jd: str) -> dict:
    keywords = extract_keywords(jd)
    cv_tokens = set(_tokens(cv))
    cv_lower = cv.lower()
    notes: list[str] = []
    total = 0.0

    # 1. Keyword matching (max ~35 pts)
    exact_matches, missing = _count_exact_keywords(cv_tokens, keywords)
    coverage = (exact_matches / len(keywords)) if keywords else 1.0
    kw_score = coverage * 30.0
    partial = _count_partial_matches(cv_lower, keywords)
    kw_score += min(partial * 2.5, 5.0)
    total += kw_score

    # 2. Sections (max ~20 pts)
    sec_score, sec_notes = _check_sections(cv_lower)
    total += sec_score
    notes.extend(sec_notes)

    # 3. Contact info (max 10 pts)
    contact_score, contact_notes = _check_contact(cv)
    total += contact_score
    notes.extend(contact_notes)

    # 4. Length / one-page (max 10 pts)
    length_score, length_notes = _check_length(cv)
    total += length_score
    notes.extend(length_notes)

    # 5. Quantified achievements (max 10 pts)
    quant_count = _count_quantified(cv)
    if quant_count >= 5:
        total += 10.0
    elif quant_count >= 3:
        total += 7.0
    elif quant_count >= 1:
        total += 4.0
    else:
        notes.append("no quantified achievements (add numbers)")

    # 6. Action verbs in bullets (max 7 pts)
    if _has_action_verbs(cv):
        total += 7.0
    else:
        notes.append("no strong action verbs found")

    # 7. Bullet points present (max 5 pts)
    bullet_count = len(re.findall(r"(?:^|\n)\s*[•\-*]\s", cv))
    if bullet_count >= 5:
        total += 5.0
    elif bullet_count >= 3:
        total += 3.5
    elif bullet_count >= 1:
        total += 2.0
    else:
        notes.append("no bullet points found (use • for achievements)")

    # 8. No pronouns (penalty)
    pronouns = re.findall(r"\b(?:I|my|me|myself)\b", cv)
    pronoun_count = len([p for p in pronouns if p.isupper() or cv_lower[cv_lower.find(p.lower())-1:cv_lower.find(p.lower())] in (" ", "\n", "")])
    if pronoun_count > 2:
        total -= 3.0
        notes.append("avoid pronouns (I, my, me) in resumes")

    # 9. Dash penalty (only flag dashes used as date separators or list markers,
    #    not compound words like "Docker-based" or phone numbers)
    if has_dashes(cv):
        stripped = cv
        stripped = re.sub(r"\d[\-\u2013\u2014]\d", "", stripped)
        stripped = re.sub(r"\b[a-zA-Z]+[\-\u2013\u2014][a-zA-Z]+\b", "", stripped)
        stripped = re.sub(r"^[\s]*[\-\u2022*]\s", "", stripped, flags=re.MULTILINE)
        if re.search(_DASH_CLASS, stripped):
            total -= 10.0
            notes.append("contains dashes (use 'to' instead)")

    final = max(0, min(100, round(total)))
    logger.debug("score=%d  kw=%d/%d  sec=%.0f  contact=%.0f  len=%.0f  quant=%d",
                 final, exact_matches, len(keywords), sec_score, contact_score,
                 length_score, quant_count)
    if missing:
        notes.append("missing keywords: " + ", ".join(missing[:10]))
    return {"score": final, "missing_keywords": missing, "notes": notes}
