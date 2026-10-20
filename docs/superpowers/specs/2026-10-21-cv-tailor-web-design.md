# CV Tailor Web — Design

Date: 2026-10-21
Status: draft for approval
Builds on: `2026-07-06-cv-generator-desktop-app-design.md` (the current desktop app)

## Intent

Today CV Tailor is a desktop app only its author can comfortably run. The goal is a
public website anyone can sign up to: paste a job link, and get back a one-page,
ATS-friendly resume in Jake's template that has passed both a real ATS check
(ResumeWorded) and an honest AI review, delivered on the site and over Telegram.

The AI work runs on the **user's own** Claude Code / Codex / Antigravity
subscription, on **their** machine, so the site owner pays nothing for AI.

Later phases (separate designs, only if this one works): auto-apply (fill the
application form, confirm with the user before submitting), then LinkedIn
outreach (HR, mutual connections, alumni, emails).

## Goals

1. Public sign-up; any user can use it.
2. Rich "master profile" per user, built once, holding far more than their current
   resume (all projects, not just the 2–3 on the resume).
3. Per job link: derive JD → tailor resume from the master profile → score on
   ResumeWorded → independent AI review → revise → repeat until done.
4. Done = ResumeWorded ATS score **> 85/100** AND reviewer score **≥ 9/10**.
5. Final PDF in Jake's template on the site + Telegram message with both scores and the PDF.
6. Missing-experience questions asked over Telegram; user replies there; loop resumes.

## Non-goals (this phase)

- Auto-apply, LinkedIn scraping/outreach, emailing HR.
- Multiple templates / template picker. Jake's template only.
- Paying for AI on the server. The server never calls an LLM.
- Mobile app.

## Anti-goals (failure even if it "works")

- **Inventing experience.** The AI may select, reorder, trim and reword facts from
  the master profile. It must never add a project, employer, metric, or skill the
  user hasn't stated. A resume that scores 95 with a fake project is a failure.
- Requiring users to understand terminals beyond a one-line install.
- Storing users' AI credentials or ResumeWorded passwords on the server.

## Architecture (decided)

```
 Browser  ──HTTPS──▶  Web server (site + API + Telegram bot)  ◀──WebSocket (outbound)──  Helper on user's machine
                                   │                                                     │
                                SQLite                                     claude / codex / agy CLI
                                                                           Playwright (ResumeWorded)
```

- **Web server** (new, `server/`): FastAPI. Serves the site, stores accounts,
  profiles, jobs, run history; runs the Telegram bot; relays jobs to the helper.
  No LLM calls. SQLite to start. *(builder's call: FastAPI + SQLite — reuses the
  Python codebase; swap to Postgres when one box isn't enough.)*
- **Helper** (evolves from current `src/`): a Python CLI the user installs once
  (`pipx install cv-tailor-agent` or a one-line install script). It opens an
  **outbound** WebSocket to the server (no ports opened on the user's machine),
  receives jobs, does all AI + browser work locally, and streams progress back.
  Reuses `src/engines/*`, `jd_fetcher`, `file_extractor`, `sanitizer`, `pdf_export`.
- **Pairing**: site shows a short one-time code; user runs `cv-tailor-agent link <code>`;
  the helper stores a per-device token in `~/.cv-tailor/`. Revocable from the site.
- **Login**: "Sign in with Google" (OAuth). *(builder's call)*
- The pywebview desktop shell (`src/app.py`, `web/`) is retired once the site works.

## Engines

Supported in the helper: `claude`, `codex`, `agy` (Antigravity CLI). Existing
Gemini/OpenCode/Ollama engines may stay but aren't advertised. A new
`src/engines/antigravity.py` follows the existing `Engine` pattern; the builder
must confirm `agy`'s headless/non-interactive flags. Helper auto-detects which CLIs
are installed and logged in (existing `Engine.check()`), reports them to the site;
user picks the default on the site.

**Reviewer** = a separate, fresh CLI invocation (no shared session with the writer)
using a reviewer prompt. Uses the same engine as the writer unless the user has a
second one installed and selects it. *(builder's call)*

## Master profile

Built once during onboarding, editable any time, stored server-side as structured
JSON (experience, projects, education, skills, achievements, certifications,
contact). Sources, all optional except the resume:

1. **Resume upload** (PDF/DOCX/TXT — existing `file_extractor`).
2. **"Ask your AI" paste**: the site shows a ready-made prompt for the user to paste
   into the AI chat they use most, e.g. *"List every project, job, internship,
   achievement, certification and skill you know about me. For each: name, what it
   does, my role, tech used, measurable results, dates, links. Don't invent
   anything."* User pastes the answer back.
3. **GitHub username**: helper (or server — no LLM needed) reads public repos
   (name, description, languages, README) via the GitHub API.
4. **LinkedIn data export** ZIP upload (Positions, Education, Skills, Projects CSVs).

The helper's AI merges all sources into the structured profile; the user reviews
and edits it on the site before it's saved. Every profile item keeps a `source`
tag so the reviewer can check claims against it.

## The tailoring loop (per job)

1. **JD**: user pastes job link on the site → helper fetches it (existing
   `jd_fetcher`; Playwright fallback) → shown on site, user can edit.
2. **Write**: writer AI gets JD + master profile + Jake's-template rules; picks the
   most relevant items and writes the resume as structured content (not free text),
   rendered to PDF by the helper.
3. **ATS check**: helper uploads the PDF + JD to ResumeWorded in a Playwright
   browser using a persistent profile in `~/.cv-tailor/browser/`. The user logs into
   their own ResumeWorded account in that browser once during onboarding. Helper
   reads back the score /100 and the listed issues.
4. **Review**: reviewer AI gets JD + master profile + resume + ResumeWorded
   feedback. Returns JSON: `score` (0–10), `issues[]`, `fabrications[]` (anything
   not backed by the profile), `missing_from_profile[]` (JD requirements the profile
   has no evidence for).
5. **Gaps**: for each `missing_from_profile` item not already asked, the bot asks
   on Telegram ("The job wants Kubernetes. Have you used it? Where?"). User replies
   in Telegram (or on the site). Answer is added to the master profile. The run
   waits for replies up to a timeout, then continues without them.
6. **Stop** when ResumeWorded > 85 **and** reviewer ≥ 9 **and** `fabrications` is
   empty. Otherwise revise using both feedbacks and go to 3.
7. **Cap**: max 6 rounds. On cap, deliver the best-scoring round with the
   reviewer's remaining notes, clearly marked "did not reach target".
8. **Deliver**: PDF + both scores on the site; Telegram message with scores and PDF.

Every round's resume, both scores and the reviewer notes are kept and shown on the
site as live progress.

## Jake's template

The de-facto standard ATS-friendly resume (single column, no tables/graphics,
sections: Education, Experience, Projects, Technical Skills; small caps headings
with a rule; bold title + right-aligned dates; italic subtitle + location). Rules
for the writer prompt encode this structure and the one-page limit.

Rendering: reproduce Jake's layout in the existing `fpdf2`-based `pdf_export`
(Latin Modern / Computer Modern–like font bundled) rather than requiring LaTeX on
user machines. *(builder's call — keeps install to one Python package.)* Text must
remain extractable (ATS parse) — verify by extracting the PDF text in a test.

## Telegram

One bot owned by the site. User taps "Connect Telegram" → deep link
`t.me/<bot>?start=<one-time token>` → server links chat ID to the account. Bot is
used for: gap questions (and receiving replies), completion message with PDF,
failure notices (helper offline, ResumeWorded login expired, engine not logged in).
Long-polling via the Bot HTTP API with `requests`; no extra framework. *(builder's call)*

## Site screens

1. Sign in.
2. Onboarding: install & link helper → pick engine → connect ResumeWorded (helper
   opens browser for login) → connect Telegram → build master profile (upload,
   AI paste, GitHub, LinkedIn ZIP) → review profile.
3. Home: paste job link, list of past jobs with status and scores.
4. Job page: JD, live round-by-round progress (scores, reviewer notes, gap
   questions), final PDF download.
5. Profile editor. 6. Settings (engine, devices, disconnects).

## Constraints & known risks

- **Helper must be running** for any job. If offline, the job queues; site and
  Telegram say so.
- **ResumeWorded** has no public API; automating its UI may breach its terms, its
  UI can change and break the scraper, and free accounts cap scans per day. The
  loop may stall on the cap. Mitigation: show the failure clearly; fall back to the
  existing local `ats_scorer` (labelled as an estimate) if the user opts in.
- **Privacy**: master profiles and resumes are personal data stored on the server.
  Need a privacy note, account deletion that removes everything, HTTPS only.
- **Abuse**: the server does no LLM work, so cost per user is small; still rate-limit
  job creation per account.

## Left to the builder

Exact schema, API routes, WebSocket message format, front-end framework (plain
HTML/JS like today is fine), hosting provider, helper packaging per OS, Telegram
reply wait timeout (suggest 30 min), how the profile JSON maps into Jake's layout.
