# CV Generator Desktop App Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A native macOS desktop app that tailors a pasted CV to a job posting URL using the local `claude` CLI (Claude Pro subscription), scores it for ATS fit, loops on user feedback until 85+, and exports an ATS friendly PDF.

**Architecture:** Python backend of small focused modules (JD fetch, prompt+generate, ATS score, sanitize, PDF). A `pywebview` native window hosts an HTML/CSS/JS 3 step wizard and calls the Python modules through a bridge `Api` object. Generation runs by piping a prompt to `claude -p` via subprocess; no API key.

**Tech Stack:** Python 3.13, pywebview, requests, beautifulsoup4, fpdf2, pytest.

## Global Constraints

- Python 3.13 via pyenv (`python3` on PATH). Node.js is broken on this machine — do not introduce any Node/Electron dependency.
- Generation engine is the local `claude` CLI in headless mode: `claude -p` with the prompt on stdin. No Anthropic API key anywhere.
- Output CV must contain **zero dash characters**: hyphen `-` (U+002D), en dash `–` (U+2013), em dash `—` (U+2014). Enforced in code, not just prompt.
- ATS score target is **85+**; scorer returns an integer 0..100.
- Keep JD keywords in output (ATS needs them) while removing robotic repetition of non keyword words.
- All shell/test commands run from repo root `/Users/apple/Documents/Projects/prepare-cv` inside the venv `.venv`.
- Each task ends with a green test run and a commit.

---

### Task 1: Project scaffold, venv, dependencies, test harness

**Files:**
- Create: `requirements.txt`
- Create: `src/__init__.py` (empty)
- Create: `tests/__init__.py` (empty)
- Create: `pytest.ini`
- Create: `tests/test_smoke.py`

**Interfaces:**
- Consumes: nothing.
- Produces: a working `.venv` with deps installed and `pytest` runnable from repo root. Import root is the repo root, so modules are imported as `from src.x import y`.

- [ ] **Step 1: Create requirements.txt**

```
pywebview==5.3.2
requests==2.32.3
beautifulsoup4==4.12.3
fpdf2==2.8.1
pytest==8.3.4
```

- [ ] **Step 2: Create pytest.ini**

```ini
[pytest]
testpaths = tests
python_files = test_*.py
```

- [ ] **Step 3: Create empty package markers**

Create `src/__init__.py` and `tests/__init__.py` as empty files.

- [ ] **Step 4: Create venv and install deps**

Run:
```bash
cd /Users/apple/Documents/Projects/prepare-cv
python3 -m venv .venv
.venv/bin/pip install -q -r requirements.txt
```
Expected: installs complete with no error. (If `pywebview` fails to build, the plan still proceeds — it is only needed at Task 8 runtime; note the failure and continue.)

- [ ] **Step 5: Write smoke test**

`tests/test_smoke.py`:
```python
def test_python_runs():
    assert 1 + 1 == 2
```

- [ ] **Step 6: Run the smoke test**

Run: `.venv/bin/pytest tests/test_smoke.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add requirements.txt pytest.ini src/__init__.py tests/__init__.py tests/test_smoke.py
git commit -m "chore: scaffold project, venv, and pytest harness"
```

---

### Task 2: Sanitizer (dash removal + repetition detection)

**Files:**
- Create: `src/sanitizer.py`
- Test: `tests/test_sanitizer.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `remove_dashes(text: str) -> str`
  - `has_dashes(text: str) -> bool`
  - `find_repeated_words(text: str, protected: set[str], threshold: int = 4) -> list[str]`
  - `STOPWORDS: set[str]`

- [ ] **Step 1: Write failing tests**

`tests/test_sanitizer.py`:
```python
from src.sanitizer import remove_dashes, has_dashes, find_repeated_words


def test_remove_em_and_en_dashes():
    assert remove_dashes("fast—paced and data–driven") == "fast paced and data driven"


def test_remove_hyphen_between_words():
    assert remove_dashes("well-organized team-player") == "well organized team player"


def test_number_range_becomes_to():
    assert remove_dashes("managed 5-10 people") == "managed 5 to 10 people"


def test_has_dashes_detects_all_kinds():
    assert has_dashes("a-b") is True
    assert has_dashes("a–b") is True
    assert has_dashes("a—b") is True
    assert has_dashes("clean text") is False


def test_find_repeated_words_flags_overuse():
    text = "led led led led team using tools"
    assert "led" in find_repeated_words(text, protected=set(), threshold=4)


def test_find_repeated_words_ignores_protected_keywords():
    text = "python python python python python"
    assert find_repeated_words(text, protected={"python"}, threshold=4) == []


def test_find_repeated_words_ignores_stopwords():
    text = "the the the the the the report"
    assert find_repeated_words(text, protected=set(), threshold=4) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_sanitizer.py -v`
Expected: FAIL (module not found).

- [ ] **Step 3: Implement sanitizer**

`src/sanitizer.py`:
```python
import re
from collections import Counter

STOPWORDS: set[str] = {
    "the", "a", "an", "and", "or", "but", "of", "to", "in", "on", "for",
    "with", "at", "by", "from", "as", "is", "are", "was", "were", "be",
    "been", "being", "this", "that", "these", "those", "it", "its", "i",
    "we", "you", "he", "she", "they", "my", "our", "your", "their", "me",
    "us", "them", "who", "which", "will", "would", "can", "could", "should",
    "has", "have", "had", "do", "does", "did", "not", "no", "so", "if",
    "than", "then", "there", "here", "up", "out", "over", "into", "about",
}

_DASH_CLASS = "[\\-–—]"


def remove_dashes(text: str) -> str:
    text = re.sub(r"(\d)\s*" + _DASH_CLASS + r"\s*(\d)", r"\1 to \2", text)
    text = re.sub(_DASH_CLASS, " ", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text


def has_dashes(text: str) -> bool:
    return bool(re.search(_DASH_CLASS, text))


def find_repeated_words(text: str, protected: set[str], threshold: int = 4) -> list[str]:
    protected_lower = {w.lower() for w in protected}
    words = re.findall(r"[a-zA-Z]+", text.lower())
    counts = Counter(
        w for w in words
        if w not in STOPWORDS and w not in protected_lower and len(w) > 2
    )
    flagged = [w for w, c in counts.items() if c >= threshold]
    return sorted(flagged, key=lambda w: counts[w], reverse=True)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_sanitizer.py -v`
Expected: PASS (all 7).

- [ ] **Step 5: Commit**

```bash
git add src/sanitizer.py tests/test_sanitizer.py
git commit -m "feat: add dash removal and repetition detection sanitizer"
```

---

### Task 3: ATS scorer (keyword extraction + scoring)

**Files:**
- Create: `src/ats_scorer.py`
- Test: `tests/test_ats_scorer.py`

**Interfaces:**
- Consumes: `from src.sanitizer import STOPWORDS, has_dashes`.
- Produces:
  - `extract_keywords(jd: str, top_n: int = 30) -> list[str]`
  - `score_cv(cv: str, jd: str) -> dict` with keys `score:int`, `missing_keywords:list[str]`, `notes:list[str]`.

- [ ] **Step 1: Write failing tests**

`tests/test_ats_scorer.py`:
```python
from src.ats_scorer import extract_keywords, score_cv


def test_extract_keywords_drops_stopwords_and_ranks_by_frequency():
    jd = "Python python python developer developer needs SQL and the the the"
    kws = extract_keywords(jd, top_n=5)
    assert "python" in kws
    assert "developer" in kws
    assert "the" not in kws
    assert kws[0] == "python"


def test_score_high_for_well_matched_cv():
    jd = "Seeking Python developer with SQL, AWS, Docker and testing experience."
    cv = (
        "Summary: Python developer.\n"
        "Experience: Built SQL pipelines on AWS using Docker.\n"
        "Skills: Python, SQL, AWS, Docker, testing.\n"
        "Education: BS Computer Science.\n"
        "Contact: jane@example.com. Increased throughput by 40%. Led testing."
    )
    result = score_cv(cv, jd)
    assert result["score"] >= 85
    assert result["missing_keywords"] == []


def test_score_reports_missing_keywords():
    jd = "Need Python, Kubernetes, and Terraform skills."
    cv = "Summary. Experience with Python. Skills: Python. Education. a@b.com"
    result = score_cv(cv, jd)
    assert "kubernetes" in result["missing_keywords"]
    assert "terraform" in result["missing_keywords"]


def test_dashes_penalize_score():
    jd = "Python developer with SQL and AWS."
    clean = "Summary. Python SQL AWS. Skills Python SQL AWS. Experience. Education. a@b.com 40%"
    dirty = clean + " fast-paced"
    assert score_cv(dirty, jd)["score"] < score_cv(clean, jd)["score"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_ats_scorer.py -v`
Expected: FAIL (module not found).

- [ ] **Step 3: Implement scorer**

`src/ats_scorer.py`:
```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_ats_scorer.py -v`
Expected: PASS (all 4).

- [ ] **Step 5: Commit**

```bash
git add src/ats_scorer.py tests/test_ats_scorer.py
git commit -m "feat: add ATS keyword extraction and scoring"
```

---

### Task 4: JD fetcher (URL fetch + HTML clean)

**Files:**
- Create: `src/jd_fetcher.py`
- Test: `tests/test_jd_fetcher.py`

**Interfaces:**
- Consumes: nothing from our modules.
- Produces:
  - `clean_html(html: str) -> str`
  - `fetch_jd(url: str, timeout: int = 20) -> str`
  - `class FetchError(Exception)`

- [ ] **Step 1: Write failing tests**

`tests/test_jd_fetcher.py`:
```python
import pytest

from src.jd_fetcher import clean_html, fetch_jd, FetchError


def test_clean_html_strips_scripts_and_collapses_whitespace():
    html = "<html><head><style>x{}</style></head><body><script>bad()</script>"\
           "<h1>Job</h1>  <p>Do   things</p></body></html>"
    out = clean_html(html)
    assert "bad()" not in out
    assert "x{}" not in out
    assert "Job" in out
    assert "Do things" in out


def test_clean_html_empty_raises():
    with pytest.raises(FetchError):
        clean_html("<html><body>   </body></html>")


def test_fetch_jd_non_200_raises(monkeypatch):
    class FakeResp:
        status_code = 403
        text = ""

    monkeypatch.setattr("src.jd_fetcher.requests.get", lambda *a, **k: FakeResp())
    with pytest.raises(FetchError):
        fetch_jd("https://example.com/job")


def test_fetch_jd_success(monkeypatch):
    class FakeResp:
        status_code = 200
        text = "<html><body><h1>Engineer</h1><p>Python role</p></body></html>"

    monkeypatch.setattr("src.jd_fetcher.requests.get", lambda *a, **k: FakeResp())
    out = fetch_jd("https://example.com/job")
    assert "Engineer" in out
    assert "Python role" in out
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_jd_fetcher.py -v`
Expected: FAIL (module not found).

- [ ] **Step 3: Implement fetcher**

`src/jd_fetcher.py`:
```python
import re

import requests
from bs4 import BeautifulSoup


class FetchError(Exception):
    pass


_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}


def clean_html(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "header", "footer", "noscript"]):
        tag.decompose()
    text = soup.get_text(separator=" ")
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        raise FetchError("no readable text found in page")
    return text


def fetch_jd(url: str, timeout: int = 20) -> str:
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=timeout)
    except requests.RequestException as exc:
        raise FetchError(f"could not reach {url}: {exc}") from exc
    if resp.status_code != 200:
        raise FetchError(
            f"site returned status {resp.status_code}; paste the job description manually"
        )
    return clean_html(resp.text)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_jd_fetcher.py -v`
Expected: PASS (all 4).

- [ ] **Step 5: Commit**

```bash
git add src/jd_fetcher.py tests/test_jd_fetcher.py
git commit -m "feat: add job description URL fetcher"
```

---

### Task 5: Generator (prompt builder + claude subprocess)

**Files:**
- Create: `src/generator.py`
- Test: `tests/test_generator.py`

**Interfaces:**
- Consumes: nothing from our modules.
- Produces:
  - `build_prompt(source_cv: str, jd: str, feedback: str = "", previous_draft: str = "", missing_keywords: list[str] | None = None) -> str`
  - `generate_cv(source_cv: str, jd: str, feedback: str = "", previous_draft: str = "", missing_keywords: list[str] | None = None, timeout: int = 180) -> str`
  - `class EngineError(Exception)`

- [ ] **Step 1: Write failing tests**

`tests/test_generator.py`:
```python
import subprocess

import pytest

from src.generator import build_prompt, generate_cv, EngineError


def test_build_prompt_includes_all_rules_and_inputs():
    p = build_prompt("MY CV", "THE JD", feedback="make it punchier",
                     previous_draft="OLD DRAFT", missing_keywords=["kubernetes", "aws"])
    assert "MY CV" in p
    assert "THE JD" in p
    assert "make it punchier" in p
    assert "OLD DRAFT" in p
    assert "kubernetes" in p and "aws" in p
    low = p.lower()
    assert "no dash" in low or "do not use dash" in low
    assert "ats" in low
    assert "repeat" in low


def test_build_prompt_minimal_no_optional_sections():
    p = build_prompt("CV", "JD")
    assert "CV" in p and "JD" in p


def test_generate_cv_returns_stripped_stdout(monkeypatch):
    class FakeCompleted:
        returncode = 0
        stdout = "  Generated CV text  "
        stderr = ""

    monkeypatch.setattr(subprocess, "run", lambda *a, **k: FakeCompleted())
    assert generate_cv("CV", "JD") == "Generated CV text"


def test_generate_cv_raises_on_nonzero_exit(monkeypatch):
    class FakeCompleted:
        returncode = 1
        stdout = ""
        stderr = "not logged in"

    monkeypatch.setattr(subprocess, "run", lambda *a, **k: FakeCompleted())
    with pytest.raises(EngineError):
        generate_cv("CV", "JD")


def test_generate_cv_raises_when_claude_missing(monkeypatch):
    def boom(*a, **k):
        raise FileNotFoundError()

    monkeypatch.setattr(subprocess, "run", boom)
    with pytest.raises(EngineError):
        generate_cv("CV", "JD")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_generator.py -v`
Expected: FAIL (module not found).

- [ ] **Step 3: Implement generator**

`src/generator.py`:
```python
import subprocess


class EngineError(Exception):
    pass


_RULES = """You are an expert resume writer. Rewrite the candidate's CV so it is
tightly tailored to the target job. Follow these rules strictly:
1. Write in natural, humanized language that reads like a real person wrote it.
   Avoid robotic or obvious AI phrasing.
2. Do NOT use any dash characters at all: no hyphen, no en dash, no em dash.
   Rephrase anything that would need one.
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_generator.py -v`
Expected: PASS (all 5).

- [ ] **Step 5: Commit**

```bash
git add src/generator.py tests/test_generator.py
git commit -m "feat: add prompt builder and claude subprocess generator"
```

---

### Task 6: PDF export (ATS friendly single column)

**Files:**
- Create: `src/pdf_export.py`
- Test: `tests/test_pdf_export.py`

**Interfaces:**
- Consumes: `from src.sanitizer import has_dashes`.
- Produces: `export_pdf(cv_text: str, out_path: str) -> str` (returns out_path). Raises `ValueError` if `cv_text` still contains dashes.

- [ ] **Step 1: Write failing tests**

`tests/test_pdf_export.py`:
```python
import os

import pytest

from src.pdf_export import export_pdf


def test_export_pdf_creates_file(tmp_path):
    out = str(tmp_path / "cv.pdf")
    cv = "Summary\nExperienced developer.\nSkills\nPython, SQL"
    result = export_pdf(cv, out)
    assert result == out
    assert os.path.exists(out)
    assert os.path.getsize(out) > 0
    with open(out, "rb") as f:
        assert f.read(4) == b"%PDF"


def test_export_pdf_rejects_dashes(tmp_path):
    out = str(tmp_path / "cv.pdf")
    with pytest.raises(ValueError):
        export_pdf("fast-paced role", out)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_pdf_export.py -v`
Expected: FAIL (module not found).

- [ ] **Step 3: Implement PDF export**

`src/pdf_export.py`:
```python
from fpdf import FPDF

from src.sanitizer import has_dashes


def export_pdf(cv_text: str, out_path: str) -> str:
    if has_dashes(cv_text):
        raise ValueError("cv_text still contains dashes; sanitize before export")

    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_margins(18, 18, 18)
    pdf.set_font("Helvetica", size=11)

    for raw_line in cv_text.split("\n"):
        line = raw_line.rstrip()
        if not line:
            pdf.ln(4)
            continue
        # A short line with no trailing period reads as a heading.
        is_heading = len(line) < 40 and not line.endswith(".")
        if is_heading:
            pdf.set_font("Helvetica", style="B", size=13)
            pdf.multi_cell(0, 7, line)
            pdf.set_font("Helvetica", size=11)
        else:
            pdf.multi_cell(0, 6, line)

    pdf.output(out_path)
    return out_path
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_pdf_export.py -v`
Expected: PASS (both).

- [ ] **Step 5: Commit**

```bash
git add src/pdf_export.py tests/test_pdf_export.py
git commit -m "feat: add ATS friendly PDF export"
```

---

### Task 7: Orchestration (the 85+ auto retry loop)

**Files:**
- Create: `src/orchestrator.py`
- Test: `tests/test_orchestrator.py`

**Interfaces:**
- Consumes: nothing at import time (dependencies injected as callables for testability).
- Produces:
  - `generate_until_target(source_cv, jd, feedback, previous_draft, generate_fn, score_fn, sanitize_fn, target=85, max_retries=3) -> dict` returning keys `cv:str`, `score:int`, `missing_keywords:list[str]`, `notes:list[str]`, `attempts:int`.
  - `generate_fn(source_cv, jd, feedback, previous_draft, missing_keywords) -> str`
  - `score_fn(cv, jd) -> dict` (same shape as `ats_scorer.score_cv`)
  - `sanitize_fn(cv) -> str` (dash free text)

- [ ] **Step 1: Write failing tests**

`tests/test_orchestrator.py`:
```python
from src.orchestrator import generate_until_target


def _score_fn_factory(scores):
    calls = {"i": 0}

    def score_fn(cv, jd):
        i = calls["i"]
        calls["i"] += 1
        s = scores[min(i, len(scores) - 1)]
        return {"score": s, "missing_keywords": ["aws"] if s < 85 else [],
                "notes": []}
    return score_fn


def test_stops_early_when_target_met():
    seen = {"count": 0}

    def generate_fn(*a, **k):
        seen["count"] += 1
        return "CV"

    result = generate_until_target(
        "cv", "jd", "", "",
        generate_fn=generate_fn,
        score_fn=_score_fn_factory([90]),
        sanitize_fn=lambda c: c,
    )
    assert result["score"] == 90
    assert result["attempts"] == 1
    assert seen["count"] == 1


def test_retries_until_target_then_stops():
    seen = {"count": 0}

    def generate_fn(*a, **k):
        seen["count"] += 1
        return "CV"

    result = generate_until_target(
        "cv", "jd", "", "",
        generate_fn=generate_fn,
        score_fn=_score_fn_factory([70, 80, 88]),
        sanitize_fn=lambda c: c,
    )
    assert result["score"] == 88
    assert result["attempts"] == 3


def test_caps_at_max_retries():
    result = generate_until_target(
        "cv", "jd", "", "",
        generate_fn=lambda *a, **k: "CV",
        score_fn=_score_fn_factory([50, 50, 50, 50, 50]),
        sanitize_fn=lambda c: c,
        max_retries=3,
    )
    assert result["attempts"] == 4  # first try + 3 retries
    assert result["score"] == 50


def test_sanitize_is_applied_to_output():
    result = generate_until_target(
        "cv", "jd", "", "",
        generate_fn=lambda *a, **k: "fast-paced",
        score_fn=_score_fn_factory([90]),
        sanitize_fn=lambda c: c.replace("-", " "),
    )
    assert result["cv"] == "fast paced"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_orchestrator.py -v`
Expected: FAIL (module not found).

- [ ] **Step 3: Implement orchestrator**

`src/orchestrator.py`:
```python
def generate_until_target(source_cv, jd, feedback, previous_draft,
                          generate_fn, score_fn, sanitize_fn,
                          target: int = 85, max_retries: int = 3) -> dict:
    attempts = 0
    missing: list[str] = []
    prev = previous_draft
    result = {"cv": "", "score": 0, "missing_keywords": [], "notes": [],
              "attempts": 0}

    while attempts <= max_retries:
        cv = sanitize_fn(generate_fn(source_cv, jd, feedback, prev, missing))
        attempts += 1
        scored = score_fn(cv, jd)
        result = {
            "cv": cv,
            "score": scored["score"],
            "missing_keywords": scored["missing_keywords"],
            "notes": scored["notes"],
            "attempts": attempts,
        }
        if scored["score"] >= target:
            break
        missing = scored["missing_keywords"]
        prev = cv
        feedback = ""  # user feedback only applies to the first attempt of a round

    return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_orchestrator.py -v`
Expected: PASS (all 4).

- [ ] **Step 5: Run the full suite**

Run: `.venv/bin/pytest -v`
Expected: PASS (all tests from Tasks 1 to 7).

- [ ] **Step 6: Commit**

```bash
git add src/orchestrator.py tests/test_orchestrator.py
git commit -m "feat: add 85+ auto retry generation orchestrator"
```

---

### Task 8: Desktop app (pywebview window, bridge API, UI, entry point)

**Files:**
- Create: `src/app.py`
- Create: `web/index.html`
- Create: `web/style.css`
- Create: `web/app.js`
- Create: `main.py`
- Test: manual (documented steps below).

**Interfaces:**
- Consumes: `src.jd_fetcher`, `src.generator`, `src.ats_scorer`, `src.sanitizer`, `src.orchestrator`, `src.pdf_export`.
- Produces: `class Api` with methods `check_engine() -> dict`, `fetch_jd(url) -> dict`, `generate(cv, jd, feedback, previous) -> dict`, `export_pdf(cv) -> dict`; and `main()` launching the window.

- [ ] **Step 1: Implement the bridge API**

`src/app.py`:
```python
import os
import subprocess
import time

import webview

from src import ats_scorer, generator, jd_fetcher, sanitizer
from src.orchestrator import generate_until_target
from src.pdf_export import export_pdf


class Api:
    def check_engine(self) -> dict:
        try:
            r = subprocess.run(["claude", "--version"], capture_output=True,
                               text=True, timeout=15)
            ok = r.returncode == 0
            return {"ok": ok, "version": r.stdout.strip()}
        except Exception as exc:  # noqa: BLE001 - report any failure to the UI
            return {"ok": False, "error": str(exc)}

    def fetch_jd(self, url: str) -> dict:
        try:
            return {"ok": True, "jd": jd_fetcher.fetch_jd(url)}
        except jd_fetcher.FetchError as exc:
            return {"ok": False, "error": str(exc)}

    def generate(self, cv: str, jd: str, feedback: str, previous: str) -> dict:
        if not cv.strip() or not jd.strip():
            return {"ok": False, "error": "Both CV and job description are required."}
        keywords = set(ats_scorer.extract_keywords(jd))

        def sanitize_fn(text: str) -> str:
            return sanitizer.remove_dashes(text)

        try:
            result = generate_until_target(
                cv, jd, feedback, previous,
                generate_fn=generator.generate_cv,
                score_fn=ats_scorer.score_cv,
                sanitize_fn=sanitize_fn,
            )
        except generator.EngineError as exc:
            return {"ok": False, "error": str(exc)}

        result["repeated_words"] = sanitizer.find_repeated_words(
            result["cv"], protected=keywords)
        result["ok"] = True
        return result

    def export_pdf(self, cv: str) -> dict:
        clean = sanitizer.remove_dashes(cv)
        out = os.path.join(os.path.expanduser("~"), "Desktop",
                           f"tailored_cv_{int(time.time())}.pdf")
        try:
            export_pdf(clean, out)
            return {"ok": True, "path": out}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc)}


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    index = os.path.join(here, "..", "web", "index.html")
    webview.create_window("CV Tailor", index, js_api=Api(),
                          width=980, height=820, min_size=(760, 620))
    webview.start()
```

- [ ] **Step 2: Create the entry point**

`main.py`:
```python
from src.app import main

if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Create the UI markup**

`web/index.html`:
```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>CV Tailor</title>
  <link rel="stylesheet" href="style.css" />
</head>
<body>
  <div id="engine-banner" class="banner hidden"></div>

  <header>
    <h1>CV Tailor</h1>
    <p class="sub">Tailor your CV to any job. Powered by your Claude subscription.</p>
  </header>

  <section id="step-input" class="card">
    <h2>1. Your details</h2>
    <label>Your current CV (paste text)</label>
    <textarea id="cv" rows="10" placeholder="Paste your CV here"></textarea>

    <label>Job posting URL</label>
    <div class="row">
      <input id="url" type="text" placeholder="https://..." />
      <button id="fetch-btn" class="secondary">Fetch JD</button>
    </div>

    <label>Job description (auto filled, or paste manually)</label>
    <textarea id="jd" rows="8" placeholder="Job description text"></textarea>

    <button id="generate-btn" class="primary">Generate tailored CV</button>
  </section>

  <section id="step-result" class="card hidden">
    <h2>2. Draft and ATS score</h2>
    <div id="score-box"></div>
    <p class="note">The ATS score is a transparent estimate based on how well
      your CV matches the job keywords and formatting. It is not an official
      score from any employer system.</p>
    <textarea id="draft" rows="16"></textarea>

    <label>Comments or changes (optional)</label>
    <textarea id="feedback" rows="3" placeholder="e.g. emphasize leadership, shorten summary"></textarea>

    <div class="row">
      <button id="regen-btn" class="secondary">Regenerate with my feedback</button>
      <button id="export-btn" class="primary">Approve and export PDF</button>
    </div>
    <div id="export-msg" class="note"></div>
  </section>

  <div id="overlay" class="overlay hidden"><div class="spinner"></div><p id="overlay-msg">Working...</p></div>

  <script src="app.js"></script>
</body>
</html>
```

- [ ] **Step 4: Create the styles**

`web/style.css`:
```css
:root { --bg:#0f1220; --card:#1a1f36; --ink:#eef1ff; --muted:#9aa3c7;
  --accent:#6c8cff; --good:#39d98a; --warn:#ffb454; }
* { box-sizing:border-box; }
body { margin:0; font-family:-apple-system,Helvetica,Arial,sans-serif;
  background:var(--bg); color:var(--ink); padding:24px; }
header h1 { margin:0 0 4px; font-size:26px; }
.sub { color:var(--muted); margin:0 0 18px; }
.card { background:var(--card); border-radius:14px; padding:20px;
  margin-bottom:18px; box-shadow:0 8px 30px rgba(0,0,0,.25); }
h2 { margin:0 0 14px; font-size:18px; }
label { display:block; margin:14px 0 6px; color:var(--muted); font-size:13px; }
textarea,input { width:100%; background:#0c0f1c; color:var(--ink);
  border:1px solid #2a3157; border-radius:10px; padding:11px; font-size:14px;
  font-family:inherit; resize:vertical; }
.row { display:flex; gap:10px; }
.row input { flex:1; }
button { border:0; border-radius:10px; padding:11px 18px; font-size:14px;
  cursor:pointer; font-weight:600; }
.primary { background:var(--accent); color:#fff; }
.secondary { background:#2a3157; color:var(--ink); }
button:disabled { opacity:.5; cursor:default; }
.primary { margin-top:16px; }
#score-box { font-size:15px; margin-bottom:8px; }
.score-num { font-size:34px; font-weight:800; }
.pill { display:inline-block; padding:3px 10px; border-radius:999px;
  font-size:12px; margin:3px 4px 0 0; background:#2a3157; }
.note { color:var(--muted); font-size:12px; margin-top:10px; }
.banner { background:var(--warn); color:#221; padding:10px 14px;
  border-radius:10px; margin-bottom:14px; }
.hidden { display:none; }
.overlay { position:fixed; inset:0; background:rgba(6,8,18,.75);
  display:flex; flex-direction:column; align-items:center; justify-content:center; }
.spinner { width:44px; height:44px; border:4px solid #2a3157;
  border-top-color:var(--accent); border-radius:50%; animation:spin 1s linear infinite; }
@keyframes spin { to { transform:rotate(360deg); } }
```

- [ ] **Step 5: Create the UI logic**

`web/app.js`:
```javascript
const $ = (id) => document.getElementById(id);
let lastDraft = "";

function showOverlay(msg) { $("overlay-msg").textContent = msg; $("overlay").classList.remove("hidden"); }
function hideOverlay() { $("overlay").classList.add("hidden"); }

async function api(name, ...args) {
  return await window.pywebview.api[name](...args);
}

window.addEventListener("pywebviewready", async () => {
  const eng = await api("check_engine");
  if (!eng.ok) {
    const b = $("engine-banner");
    b.textContent = "Claude engine not ready. Open Terminal, run `claude`, and log in with your Claude account, then reopen this app.";
    b.classList.remove("hidden");
  }
});

$("fetch-btn").onclick = async () => {
  const url = $("url").value.trim();
  if (!url) return;
  showOverlay("Fetching job description...");
  const r = await api("fetch_jd", url);
  hideOverlay();
  if (r.ok) { $("jd").value = r.jd; }
  else { alert(r.error + "\n\nPaste the job description manually instead."); }
};

function renderScore(r) {
  const color = r.score >= 85 ? "var(--good)" : "var(--warn)";
  let html = `<span class="score-num" style="color:${color}">${r.score}</span> / 100 ATS match`;
  if (r.missing_keywords && r.missing_keywords.length) {
    html += `<div class="note">Still missing keywords:</div>`;
    html += r.missing_keywords.slice(0, 12).map(k => `<span class="pill">${k}</span>`).join("");
  }
  if (r.repeated_words && r.repeated_words.length) {
    html += `<div class="note">Overused words toned down next round: ${r.repeated_words.join(", ")}</div>`;
  }
  $("score-box").innerHTML = html;
}

async function runGenerate(feedback) {
  const cv = $("cv").value, jd = $("jd").value;
  showOverlay("Generating and scoring. This runs a few passes to reach 85+...");
  const r = await api("generate", cv, jd, feedback || "", lastDraft);
  hideOverlay();
  if (!r.ok) { alert(r.error); return; }
  lastDraft = r.cv;
  $("draft").value = r.cv;
  renderScore(r);
  $("step-result").classList.remove("hidden");
  $("step-result").scrollIntoView({ behavior: "smooth" });
}

$("generate-btn").onclick = () => { lastDraft = ""; runGenerate(""); };
$("regen-btn").onclick = () => {
  lastDraft = $("draft").value;  // respect manual edits as the base
  runGenerate($("feedback").value);
};

$("export-btn").onclick = async () => {
  showOverlay("Exporting PDF...");
  const r = await api("export_pdf", $("draft").value);
  hideOverlay();
  $("export-msg").textContent = r.ok ? `Saved to ${r.path}` : `Error: ${r.error}`;
};
```

- [ ] **Step 6: Manual smoke test of the window**

Run: `.venv/bin/python main.py`
Expected: a native window titled "CV Tailor" opens showing the input form. If `claude` is logged in, no warning banner appears. Close the window to end.

- [ ] **Step 7: Manual end to end test**

With the window open:
1. Paste a short sample CV into the CV box.
2. Paste a short sample job description into the JD box (skip the URL to keep the test offline).
3. Click **Generate tailored CV**. Wait for the overlay to clear.
4. Confirm a draft appears, a score shows, and the draft contains no dash characters.
5. Type a comment and click **Regenerate**; confirm the draft updates.
6. Click **Approve and export PDF**; confirm a message shows a path on the Desktop and the PDF opens.

- [ ] **Step 8: Commit**

```bash
git add src/app.py main.py web/index.html web/style.css web/app.js
git commit -m "feat: add pywebview desktop window, bridge API, and wizard UI"
```

---

### Task 9: README and run instructions

**Files:**
- Create: `README.md`

**Interfaces:**
- Consumes: nothing.
- Produces: user facing run instructions.

- [ ] **Step 1: Write README**

`README.md`:
```markdown
# CV Tailor

A macOS desktop app that tailors your CV to a job posting using your Claude
subscription (via the local `claude` CLI). It scores the result for ATS fit,
loops until it reaches 85+, lets you give feedback, and exports a clean PDF.

## Requirements

- macOS
- Python 3.13
- Claude Code CLI installed and logged in: run `claude` once in Terminal and
  sign in with your Claude account. No API key needed.

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Run

```bash
.venv/bin/python main.py
```

## How it works

1. Paste your CV and a job posting URL (or paste the job description).
2. The app generates a tailored CV with your Claude subscription.
3. It scores the CV against the job and auto improves until it reaches 85+.
4. Review, comment, and regenerate as many times as you like.
5. Approve to export an ATS friendly PDF to your Desktop.

The ATS score is a transparent estimate based on keyword coverage and
formatting. It is not an official score from any employer system.

## Tests

```bash
.venv/bin/pytest -v
```
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add README with setup and run instructions"
```

---

## Self-Review Notes

- **Spec coverage:** JD fetch (T4), generator via claude CLI (T5), ATS scorer (T3), sanitizer dash+repetition (T2), PDF export (T6), 85+ loop (T7), pywebview UI + bridge (T8), error handling (typed errors surfaced in T4/T5/T8), honesty note on score (UI T8, README T9). All spec sections mapped.
- **Placeholders:** none; every code and test step is complete.
- **Type consistency:** `score_cv` returns `{score, missing_keywords, notes}` in T3 and is consumed with those exact keys in T7 and T8. `generate_cv` signature in T5 matches the `generate_fn` contract in T7. `remove_dashes`/`has_dashes`/`find_repeated_words` names consistent across T2, T3, T6, T8.
```
