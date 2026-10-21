# Helper Tailoring Loop Implementation Plan (Plan 1 of 4)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A terminal command that builds a master profile and runs the write → ATS score → independent review → revise loop until ATS > 85 and review ≥ 9/10, producing a Jake's-template PDF.

**Architecture:** Pure-Python modules in `src/` with the LLM, ATS scorer, and gap-asker injected as callables so the loop is testable with fakes. The ATS scorer here is the existing local `ats_scorer` (ResumeWorded arrives in Plan 4); gap questions go to the terminal (`input()`), Telegram arrives in Plan 3; the server/site arrives in Plan 2.

**Tech Stack:** Python 3.10+, existing `src/engines`, `src/pdf_export` (already Jake-style), `requests`, `pytest`.

**Spec:** `docs/superpowers/specs/2026-10-21-cv-tailor-web-design.md`

Later plans: 2 = server + site + helper pairing, 3 = Telegram, 4 = ResumeWorded automation.

## Global Constraints

- Done = ATS score **> 85** AND reviewer score **≥ 9** AND reviewer `fabrications` empty.
- Max **6** rounds; on cap return the best round with `reached_target=False`.
- Never invent experience: writer may only select/reorder/trim/reword profile facts.
- Jake's section order: Name, Contact, Education, Experience, Projects, Technical Skills. One page.
- Engines advertised: `claude`, `codex`, `agy`. Each LLM call is a fresh CLI invocation (reviewer never shares a session with the writer).
- No new dependencies.

## Review Focus

1. LLM wraps JSON in prose or ```json fences → `parse_json` must still extract it (Task 2 test).
2. LLM returns unparseable JSON → one retry, then a clear `ValueError` naming the step (Task 2 test).
3. Reviewer score returned as `"9/10"` or `"8.5"` → normalised to float (Task 3 test).
4. Non-Latin-1 characters (smart quotes, em dash, "é") in profile text → PDF still renders (Task 5 test).
5. The same gap asked twice across rounds → asked once only (Task 4 test).

---

### Task 1: Antigravity engine

**Files:**
- Create: `src/engines/antigravity.py`
- Modify: `src/engines/__init__.py` (add `"agy"` to `ENGINE_MAP`, `ENGINE_LABELS` = "Antigravity", `DEFAULT_MODELS` = `"claude-sonnet-4-6"`)
- Test: `tests/test_engines.py`

**Interfaces:** Produces: `get_engine("agy")` → Engine with `_binary_names() == ["agy"]`, `_generate_args(m) == ["--model", m, "-p"]`, `_send_prompt_via_stdin() is False` (verified: `agy -p` takes the prompt as the next argument; stdin is ignored).

- [ ] Step 1: test `test_agy_engine_args` asserting the three values above.
- [ ] Step 2: run `pytest tests/test_engines.py -k agy -v` → FAIL.
- [ ] Step 3: implement, mirroring `src/engines/claude.py`.
- [ ] Step 4: run → PASS. Step 5: commit `feat: add Antigravity (agy) engine`.

### Task 2: LLM call + JSON parsing

**Files:** Create `src/llm.py`; Test `tests/test_llm.py`

**Interfaces:** Produces:
- `parse_json(text: str) -> dict` — strips ``` fences, else takes the first `{` to the last `}`; raises `ValueError` if no valid object.
- `make_llm(engine: str, model: str | None = None, timeout: int = 300) -> Callable[[str], str]` — wraps `get_engine(engine).generate`.
- `ask_json(llm: Callable[[str], str], prompt: str, step: str) -> dict` — calls `llm`, parses; on `ValueError` retries once appending "Return ONLY valid JSON."; second failure raises `ValueError(f"{step}: model did not return valid JSON")`.

- [ ] Tests: `test_parse_json_fenced`, `test_parse_json_with_prose`, `test_ask_json_retries_once_then_succeeds`, `test_ask_json_raises_after_two_failures` (fake llm list of outputs).
- [ ] Run fail → implement → run pass → commit `feat: llm json helper`.

### Task 3: Profile builder, writer, reviewer prompts

**Files:** Create `src/profile.py`, `src/tailor.py`; Test `tests/test_profile.py`, `tests/test_tailor.py`

**Interfaces:**
- `profile.AI_PASTE_PROMPT: str` — exact copy: *"List every project, job, internship, achievement, certification and skill you know about me. For each: name, what it does, my role, tech used, measurable results, dates, links. Don't invent anything; say 'unknown' where you don't know."*
- `profile.github_text(username: str) -> str` — GET `https://api.github.com/users/{u}/repos?per_page=100&sort=updated`, skip forks, one line per repo: name, description, language, html_url.
- `profile.linkedin_text(zip_path: str) -> str` — concatenates `Positions.csv`, `Education.csv`, `Skills.csv`, `Projects.csv` if present (zipfile + csv stdlib).
- `profile.build_profile(sources: dict[str, str], llm) -> dict` — `ask_json` with a merge prompt; returns `{"contact": {...}, "education": [], "experience": [], "projects": [], "skills": {}, "achievements": [], "certifications": []}`; every list item has `"source"`.
- `tailor.write_resume(profile: dict, jd: str, llm, feedback: str = "", previous: str = "") -> str` — plain text in the format `pdf_export` already renders (reuse `generator._RULES` formatting block + "use only facts from PROFILE").
- `tailor.review_resume(profile: dict, jd: str, resume: str, ats: dict, llm) -> dict` → `{"score": float, "issues": list[str], "fabrications": list[str], "missing_from_profile": list[str]}`; score normalised: `"9/10"`→9.0, `"8.5"`→8.5.

- [ ] Tests: `test_linkedin_text_reads_positions` (build zip in tmp_path), `test_build_profile_returns_schema_keys` (fake llm), `test_write_prompt_contains_profile_and_no_invent_rule` (capture prompt), `test_review_normalises_score_strings`, `test_review_defaults_missing_lists_to_empty`.
- [ ] Run fail → implement → run pass → commit `feat: profile builder, writer and reviewer`.

### Task 4: The loop

**Files:** Create `src/tailor_loop.py`; Test `tests/test_tailor_loop.py`

**Interfaces:**
- `run(profile: dict, jd: str, *, write, review, ats, ask_gaps, on_round=lambda r: None, max_rounds: int = 6) -> dict`
  - `write(profile, jd, feedback, previous) -> str`; `ats(resume_text, jd) -> {"score": int, "issues": list[str]}`; `review(profile, jd, resume, ats_result) -> dict` (Task 3 shape); `ask_gaps(questions: list[str]) -> dict[str, str]` answers (may be empty).
  - Each round dict: `{"round", "resume", "ats", "review"}` passed to `on_round`.
  - Gap answers are appended to `profile["achievements"]`-independent list `profile["user_answers"]` as `{"question", "answer", "source": "user"}`; a question is never asked twice.
  - Feedback to next write = ATS issues + reviewer issues + fabrications ("remove: …").
  - Returns `{"resume", "ats", "review", "rounds": [...], "reached_target": bool}`; best round = highest `(passes, review.score + ats.score/10)`.

- [ ] Tests: `test_stops_when_both_targets_met`, `test_ats_85_exactly_does_not_pass`, `test_fabrications_block_done`, `test_caps_at_six_and_returns_best`, `test_gap_asked_once_and_saved_to_profile`.
- [ ] Run fail → implement → run pass → commit `feat: tailoring loop`.

### Task 5: Terminal command

**Files:** Create `src/agent.py`; Modify `src/pdf_export.py` (latin-1 safety in `export_pdf`); Test `tests/test_agent.py`, `tests/test_pdf_export.py`

**Interfaces:**
- `python -m src.agent prompt` → prints `AI_PASTE_PROMPT`.
- `python -m src.agent profile --resume PATH [--github USER] [--linkedin ZIP] [--ai-paste FILE] [--engine agy] -o profile.json`
- `python -m src.agent run --profile profile.json (--job URL | --jd-file FILE) [--engine agy] [--reviewer-engine claude] [-o out.pdf]` — prints each round (`round 2: ATS 81 · review 7.5/10`), gap questions via `input()`, saves updated profile back, writes PDF via `export_pdf`, prints path and whether target was reached.
- `export_pdf` maps “ ” ‘ ’ — – … to ASCII and encodes remaining text `latin-1` with `errors="replace"`.

- [ ] Tests: `test_export_pdf_handles_unicode` (text with “smart” quotes, é, emoji → file exists, >0 bytes), `test_agent_run_with_fakes` (monkeypatch `make_llm` and fetch; asserts PDF written and profile file updated).
- [ ] Run fail → implement → run pass → full suite `pytest -q` → commit `feat: cv-tailor agent CLI`.
- [ ] Manual: `python -m src.agent run --profile <real profile> --jd-file <jd> --engine agy` end to end once.
