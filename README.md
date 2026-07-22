# CV Tailor

A desktop app that tailors your CV to any job posting using AI. Pick your engine — Claude, Gemini, or Codex — and let it generate an ATS-optimized CV, score it, and loop until it hits 85+.

## Features

- **Multi-engine support** — Use Claude Code, Gemini CLI, Codex CLI, OpenCode, or Ollama (local)
- **Smart JD fetching** — Auto-detects Greenhouse, Lever, and other ATS platforms; falls back to Playwright for JS-rendered pages
- **ATS scoring** — Keyword matching, section checks, formatting analysis
- **Auto-iteration** — Loops until the ATS score reaches 85+
- **PDF export** — Clean, one-page ATS-friendly PDF to your Desktop
- **Cross-platform** — macOS, Windows, and Linux

## Requirements

- Python 3.10+
- **At least one** AI CLI installed and authenticated:
  - [Claude Code](https://docs.anthropic.com/en/docs/claude-code): `npm install -g @anthropic-ai/claude-code` then run `claude` and log in
  - [Gemini CLI](https://github.com/google-gemini/gemini-cli): `npm install -g @google/gemini-cli` then run `gemini` and log in
  - [Codex CLI](https://github.com/openai/codex): `npm install -g @openai/codex` then run `codex` and log in
  - [OpenCode](https://opencode.ai): ships free zen models that work with no login; run `opencode auth login` to add your own provider
  - [Ollama](https://ollama.com) (local models): install Ollama, then pull a model first, e.g. `ollama pull llama3.2`. Caution: runs on your machine and can be slow on CPU or with large models.
- Playwright (for JS-rendered job pages): `pip install playwright && playwright install chromium`

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium  # one-time, for JD fetching
```

## Run

```bash
python main.py
```

1. Click the **gear icon** (top right) to select your AI engine and model
2. Paste your CV and a job posting URL (or paste the JD manually)
3. The app generates a tailored CV, scores it, and iterates to 85+
4. Review, give feedback, and regenerate as many times as you like
5. Approve to export an ATS-friendly PDF to your Desktop

## How it works

| Step | What happens |
|------|-------------|
| Fetch JD | Tries Greenhouse/Lever API first, then Playwright, then plain HTTP |
| Generate | Sends your CV + JD to the selected AI engine with strict formatting rules |
| Score | Analyzes keyword coverage, sections, contact info, length, action verbs |
| Iterate | If score < 85, feeds missing keywords back and regenerates |
| Export | Renders a clean A4 PDF with proper typography |

The ATS score is a transparent estimate. It is not an official score from any employer system.

## Settings

Your preferences are saved to `~/.cv-tailor/settings.json`:

```json
{
  "engine": "claude",
  "model": "sonnet",
  "max_generations": 6,
  "timeout_seconds": 300
}
```

`timeout_seconds` is the per-generation limit for the AI CLI. Raise it if long job descriptions time out; lower it to fail faster. A full CV rewrite with a hosted model typically takes 30 to 60 seconds.

Logs are written to `~/.cv-tailor/cv-tailor.log`, and the app has a **Logs** button (bottom right) that streams progress live during generation and JD fetching.

## Tests

```bash
pytest -v
```

## License

MIT
