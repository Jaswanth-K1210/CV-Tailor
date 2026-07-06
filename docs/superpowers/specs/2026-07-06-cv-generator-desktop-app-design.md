# CV Generator Desktop App — Design

**Date:** 2026-07-06
**Status:** Approved (pending spec review)

## Purpose

A macOS desktop app that takes the user's existing CV and a target job posting,
then generates a tailored, ATS friendly CV using the local `claude` CLI (powered
by the user's Claude Pro subscription, no API key). The user reviews each draft
with an ATS score, gives feedback, and regenerates until satisfied, then exports
a clean PDF.

## Key Decisions

- **Engine:** Local `claude` CLI in headless mode (`claude -p`). Uses the user's
  Claude Pro subscription. No Anthropic API key, no per token billing. Verified
  working on this machine (`claude` v2.1.179).
- **Language:** Python 3.13 (via pyenv). Node.js is currently broken on this
  machine (Homebrew `llhttp` mismatch), so Electron is avoided.
- **UI shell:** `pywebview` native macOS window wrapping an HTML/CSS/JS UI.
- **CV input:** pasted plain text.
- **JD input:** job posting URL (auto fetched); manual paste fallback.
- **Output:** copyable text plus an ATS friendly single column PDF (`fpdf2`).

## Rules (baked into prompt AND enforced in code)

1. **ATS score target 85+.** After each generation the app scores the CV. If
   below 85 it feeds the missing keywords back to Claude and regenerates, up to
   3 silent retries, before showing the user.
2. **Humanized, natural wording.** No robotic AI phrasing.
3. **Strictly no dashes.** Every em dash, en dash, and hyphen is removed by the
   sanitizer; hyphen joined phrases are rewritten. Approval is blocked if any
   dash remains (auto fixed).
4. **No robotic word repetition.** Overused non keyword words are flagged and
   fed back for rewrite. Important JD keywords are protected (ATS rewards them).

## Architecture

Small, independently testable modules:

### `jd_fetcher.py`
- **Does:** fetch a job posting URL, extract and clean the JD text.
- **How:** `requests` + `beautifulsoup4`. Strips nav/script/style, collapses
  whitespace. Returns cleaned text.
- **Failure:** on non 200, block (403), or empty extraction, raise a typed error
  so the UI can prompt the user to paste the JD manually.

### `generator.py`
- **Does:** build the generation prompt and call `claude -p`, return CV text.
- **How:** `subprocess.run(["claude", "-p"], input=prompt, ...)`. Prompt bundles:
  the source CV, the JD, the rules (humanized, no dashes, ATS keywords, no
  repetition), the previous draft (if any), the user's feedback (if any), and
  the list of missing keywords (if any).
- **Pure part:** `build_prompt(...)` is a pure function, unit tested without
  spending Claude usage. The subprocess call is a thin wrapper, tested with a
  mocked subprocess.
- **Failure:** missing/unauthenticated `claude`, timeout, non zero exit ->
  typed errors surfaced to the UI.

### `ats_scorer.py`
- **Does:** compute a 0..100 score and a breakdown.
- **How:** extract keywords from the JD (tokenize, drop stopwords, weight by
  frequency, detect multi word skills). Score components:
  - keyword coverage (dominant weight),
  - required sections present (summary, experience, skills, education),
  - contact info present,
  - reasonable length,
  - action verb / quantified bullet presence,
  - dash compliance.
- **Returns:** `score:int`, `missing_keywords:list[str]`, `notes:list[str]`.
- Score is a transparent estimate, labeled as such in the UI. It is not a real
  Workday/Greenhouse internal score.

### `sanitizer.py`
- **Does:** enforce no dashes and detect robotic repetition.
- **How:** replace/remove `– — -` and rewrite hyphen joined tokens; compute
  frequency of non stopword, non keyword words and flag overuse.
- **Returns:** cleaned text plus a list of overused words for feedback.

### `pdf_export.py`
- **Does:** render final CV text to an ATS friendly single column PDF.
- **How:** `fpdf2` (pure Python, no system libs). Plain fonts, clear section
  headings, no graphics/columns/tables (ATS parsers prefer this).
- **Guarantee:** asserts the exported text contains no dash characters.

### `app.py`
- **Does:** create the pywebview window and expose a bridge API to the UI:
  `fetch_jd(url)`, `generate(cv, jd, feedback, prev)`, `score(cv, jd)`,
  `export_pdf(cv, path)`, `check_engine()`.
- Orchestrates the 85+ auto retry loop server side.

### `web/` UI
- 3 step wizard: **Inputs** (CV + URL) -> **Draft** (draft text + score +
  missing items + feedback box + regenerate) -> **Export** (PDF).
- Modern, clean styling. Shows the ATS score prominently with its breakdown.

## Data Flow

paste CV + URL -> fetch JD (or paste) -> build prompt -> `claude -p` -> sanitize
-> score -> if <85 auto retry (<=3) -> show draft + score + missing -> user
feedback -> regenerate -> repeat until approved -> export PDF.

## Error Handling

- `claude` missing or not logged in: clear on screen fix instructions.
- JD URL blocked/failed: prompt manual JD paste.
- Generation timeout/error: friendly message + retry.
- Empty CV/URL: input validation before generating.
- PDF write failure: surface the path/permission issue.

## Testing

- **Unit (test first):**
  - `ats_scorer`: known JD/CV -> expected keyword extraction and score band.
  - `sanitizer`: dash removal, hyphen rewrite, repetition detection.
  - `jd_fetcher`: mocked HTML -> clean text; error cases raise typed errors.
  - `generator.build_prompt`: includes all required sections/rules (pure).
  - `pdf_export`: file created, contains no dash characters.
- **Integration/manual:** full app run end to end via pywebview.

## Out of Scope (YAGNI)

- Multiple CV templates/themes.
- Cloud sync, accounts, storage of past CVs.
- DOCX export.
- Windows/Linux packaging (macOS first).
