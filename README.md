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
