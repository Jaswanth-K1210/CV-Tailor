# Server + Website + Helper Linking Implementation Plan (Plan 2 of 4)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A website where a user signs in, links their computer's helper, builds their master profile, pastes a job link, watches each round live, answers gap questions, and downloads the PDF; the AI work runs in the helper on their machine.

**Architecture:** FastAPI + stdlib `sqlite3` in `server/`, plain HTML/JS front end in `server/static/`. The helper is a loop in `src/worker.py` that **long-polls over HTTPS** with `requests` (decided over WebSocket: no new client dependency, survives proxies, same "no inbound ports" property). The browser polls job status every 2 s. Gap questions are answered on the site in this plan; Plan 3 adds Telegram on the same answer endpoint.

**Tech Stack:** FastAPI, uvicorn, python-multipart (uploads), httpx (TestClient only), existing `src/*`.

**Spec:** `docs/superpowers/specs/2026-10-21-cv-tailor-web-design.md`

## Global Constraints

- Server never calls an LLM.
- Login: Google Sign-In ID token verified via `https://oauth2.googleapis.com/tokeninfo` (`aud` must equal env `GOOGLE_CLIENT_ID`). Dev login `POST /api/auth/dev` exists only when env `CVT_DEV_LOGIN=1`.
- Sessions: random 32-byte token in `sessions` table, `HttpOnly; SameSite=Lax` cookie `cvt_session` (`Secure` when `CVT_SECURE_COOKIES=1`).
- Device tokens: random 32 bytes, stored hashed (sha256); sent as `Authorization: Bearer`. Pairing code: 6 chars from `ABCDEFGHJKLMNPQRSTUVWXYZ23456789`, valid 10 min, single use.
- Every user-data query is scoped by `user_id`; a user can never read another user's job/profile/PDF.
- Gap-answer wait: 30 min, then the run continues without answers.
- Rate limit: max 20 jobs per user per 24 h.
- `DELETE /api/me` removes all the user's rows and files.
- Data dir: env `CVT_DATA` (default `./data`): `cvt.db`, `pdfs/<job_id>.pdf`.

## Review Focus

1. User A requests user B's job / PDF by id → 404 (Task 2 test).
2. Two helpers polling at once for one user → each job is claimed by exactly one (Task 3 test: claim is an atomic `UPDATE … WHERE status='queued'`).
3. Helper crashes mid-job → job stays `running` forever; the site shows "helper last seen N min ago" from `devices.last_seen` (Task 3 test: `last_seen` updated on poll).
4. Reused or expired pairing code → 400 (Task 3 test).
5. Gap question nobody answers → worker gets `{}` after timeout and the loop continues (Task 4 test with timeout=0).

---

### Task 1: Database

**Files:** Create `server/__init__.py`, `server/db.py`; Test `tests/test_server_db.py`

**Interfaces:** Produces `db.connect(path: str) -> sqlite3.Connection` (row_factory=Row, foreign keys on, creates schema). Tables:
- `users(id, email UNIQUE, name, engine DEFAULT 'claude', profile_json, sources_json, created_at)`
- `sessions(token PRIMARY KEY, user_id, created_at)`
- `pair_codes(code PRIMARY KEY, user_id, expires_at, used)`
- `devices(id, user_id, token_hash UNIQUE, engines_json, last_seen)`
- `jobs(id, user_id, kind 'tailor'|'profile', status 'queued'|'running'|'waiting'|'done'|'failed', job_url, jd, payload_json, result_json, error, created_at, updated_at)`
- `events(id, job_id, ts, type, data_json)`; `questions(id, job_id, text, answer, asked_at, answered_at)`
All child tables `ON DELETE CASCADE` from users.

- [ ] test `test_schema_and_cascade_delete`: insert user + job + event; delete user; jobs/events empty.
- [ ] fail → implement → pass → commit.

### Task 2: Auth + user API

**Files:** Create `server/app.py`; Test `tests/test_server_api.py`

**Interfaces:** `app.create_app(data_dir: str) -> FastAPI`. Routes (JSON):
- `POST /api/auth/google {credential}`; `POST /api/auth/dev {email}`; `POST /api/auth/logout`; `GET /api/me` → `{email, name, engine, has_profile, devices:[{id, engines, last_seen}], telegram: false}`; `PUT /api/me {engine}`; `DELETE /api/me`.
- `POST /api/jobs {job_url?, jd?}` → `{id}`; `GET /api/jobs` → list; `GET /api/jobs/{id}` → job + events + open questions; `POST /api/jobs/{id}/answers {question_id: answer}`; `GET /api/jobs/{id}/pdf`.
- `GET /api/profile`, `PUT /api/profile {profile}`, `POST /api/profile/sources` (multipart: `resume` file, `linkedin` zip, `github`, `ai_paste`) → stores extracted text in `sources_json`, queues a `profile` job.
- `GET /` serves `static/index.html`.

- [ ] tests: `test_dev_login_sets_cookie_and_me_works`, `test_dev_login_disabled_without_env`, `test_other_users_job_is_404`, `test_job_rate_limit_20_per_day`, `test_delete_me_removes_pdf_file`, `test_google_login_rejects_wrong_aud` (monkeypatch `requests.get`).
- [ ] fail → implement → pass → commit.

### Task 3: Helper pairing + agent API

**Files:** Modify `server/app.py`; Test `tests/test_server_agent.py`

**Interfaces:**
- `POST /api/devices/code` (session) → `{code, expires_in: 600}`.
- `POST /api/agent/link {code, engines}` → `{token}`.
- `GET /api/agent/next?wait=25` (bearer) → `{job: {id, kind, job_url, jd, engine, profile, sources}}` or `{job: null}`; claims atomically, updates `devices.last_seen` and `engines_json`.
- `POST /api/agent/jobs/{id}/event {type, data}` — types: `jd`, `round`, `log`; `jd` also stores `jobs.jd`.
- `POST /api/agent/jobs/{id}/questions {questions:[str]}` → `{ids}`; status → `waiting`.
- `GET /api/agent/jobs/{id}/answers` → `{answers: {text: answer}, pending: n}`.
- `POST /api/agent/jobs/{id}/finish` multipart: `result` JSON, optional `pdf` file, optional `profile` JSON (saved to user) → status `done`/`failed`.

- [ ] tests: `test_link_with_code_once`, `test_expired_code_rejected`, `test_claim_is_exclusive`, `test_poll_updates_last_seen`, `test_agent_cannot_touch_other_users_job`, `test_finish_stores_pdf_and_profile`.
- [ ] fail → implement → pass → commit.

### Task 4: Worker (helper side)

**Files:** Create `src/worker.py`; Modify `src/agent.py` (add `link` and `serve` subcommands); Test `tests/test_worker.py`

**Interfaces:**
- Config file `~/.cv-tailor/agent.json` `{server, token}`.
- `worker.link(server: str, code: str) -> None`; `worker.serve(server, token, once=False)`.
- `worker.handle_job(api, job) -> None` where `api` is a small object with `event(type, data)`, `ask(questions) -> dict`, `finish(result, pdf_path=None, profile=None)`; `kind='profile'` → `profile.build_profile(job['sources'], llm)`; `kind='tailor'` → fetch JD if needed, run `tailor_loop.run` with `local_ats`, `on_round` → `event('round', …)`, `ask_gaps` → `api.ask` (polls answers every 5 s up to 30 min).
- `python -m src.agent link CODE --server URL`; `python -m src.agent serve`.

- [ ] tests: `test_handle_tailor_job_reports_rounds_and_finishes` (fake api + monkeypatched llm), `test_ask_returns_empty_after_timeout`, `test_handle_job_failure_reports_error`.
- [ ] fail → implement → pass → commit.

### Task 5: Website

**Files:** Create `server/static/index.html`, `server/static/app.js`, `server/static/style.css`; `server/__main__.py` (`python -m server` runs uvicorn on `$PORT` or 8000).

Screens (hash routes): `#/login` (Google button via `accounts.google.com/gsi/client`, dev form when dev login on), `#/setup` (pairing code + copyable `python -m src.agent link CODE --server <origin>`; engine select from linked device's engines; profile sources form with the AI-paste prompt and copy button), `#/profile` (JSON editor textarea + save — ponytail: structured editor later), `#/` (job link input + job list with status/scores), `#/job/:id` (rounds table: ATS, review, issues; open questions with answer boxes; PDF download; "helper last seen").

- [ ] Manual check: `CVT_DEV_LOGIN=1 python -m server`, then `python -m src.agent link …` and `serve`; sign in, link, build profile, run a job end-to-end in the browser; screenshot each screen.
- [ ] Commit.
