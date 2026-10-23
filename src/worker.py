"""Helper side of the website: link this computer, then poll for jobs and run them."""
from __future__ import annotations

import json
import logging
import os
import tempfile
import time
from pathlib import Path

import requests

from src import agent, jd_fetcher
from src import profile as profile_mod
from src.engines import get_engine
from src.resume_pdf import render_pdf

logger = logging.getLogger(__name__)

CONFIG = Path.home() / ".cv-tailor" / "agent.json"
SUPPORTED = ("claude", "codex", "agy")
ANSWER_TIMEOUT = 30 * 60


def installed_engines() -> list[str]:
    return [n for n in SUPPORTED if get_engine(n).check().get("ok")]


def load_config() -> dict:
    return json.loads(CONFIG.read_text()) if CONFIG.exists() else {}


def link(server: str, code: str) -> None:
    server = server.rstrip("/")
    r = requests.post(f"{server}/api/agent/link",
                      json={"code": code, "engines": installed_engines()}, timeout=20)
    if not r.ok:
        raise SystemExit(r.json().get("detail", r.text))
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    CONFIG.write_text(json.dumps({"server": server, "token": r.json()["token"]}))
    os.chmod(CONFIG, 0o600)
    print(f"Linked to {server}. Now run: python -m src.agent serve")


class Api:
    def __init__(self, server: str, token: str, job_id: int):
        self.base = f"{server}/api/agent/jobs/{job_id}"
        self.headers = {"Authorization": f"Bearer {token}"}

    def event(self, type_: str, data) -> None:
        requests.post(f"{self.base}/event", json={"type": type_, "data": data},
                      headers=self.headers, timeout=20).raise_for_status()

    def ask(self, questions: list[str], timeout: float = ANSWER_TIMEOUT,
            poll: float = 5) -> dict[str, str]:
        requests.post(f"{self.base}/questions", json={"questions": questions},
                      headers=self.headers, timeout=20).raise_for_status()
        deadline = time.time() + timeout
        while True:
            got = requests.get(f"{self.base}/answers", headers=self.headers, timeout=20).json()
            if got["pending"] == 0 or time.time() >= deadline:
                return got["answers"]
            time.sleep(poll)

    def finish(self, result: dict, pdf_path: str | None = None,
               profile: dict | None = None) -> None:
        data = {"result": json.dumps(result)}
        if profile is not None:
            data["profile"] = json.dumps(profile)
        files = None
        if pdf_path:
            files = {"pdf": ("resume.pdf", open(pdf_path, "rb"), "application/pdf")}
        try:
            requests.post(f"{self.base}/finish", data=data, files=files,
                          headers=self.headers, timeout=60).raise_for_status()
        finally:
            if files:
                files["pdf"][1].close()


def handle_job(api, job: dict) -> None:
    try:
        if job["kind"] == "profile":
            sources = dict(job["sources"])
            gh = sources.pop("github_user", None)
            if gh:
                api.event("log", {"msg": f"reading GitHub repos of {gh}"})
                try:
                    sources["github"] = profile_mod.github_text(gh)
                except Exception as exc:
                    # GitHub is optional; build the profile from the other sources.
                    api.event("log", {"msg": f"skipped GitHub ({exc})"})
            api.event("log", {"msg": "merging your sources into a master profile"})
            prof = profile_mod.build_profile(sources, agent.make_llm(job["engine"]))
            api.finish({"ok": True}, profile=prof)
            return

        jd = job.get("jd")
        if not jd:
            api.event("log", {"msg": "fetching the job description"})
            jd = jd_fetcher.fetch_jd(job["job_url"])
            api.event("jd", {"jd": jd})
        prof = job["profile"]

        result = agent.tailor_job(prof, jd, job["engine"], None, ask_gaps=api.ask,
                                  on_round=lambda r: api.event("round", r))
        with tempfile.TemporaryDirectory() as tmp:
            pdf = os.path.join(tmp, "resume.pdf")
            render_pdf(result["resume"], pdf)
            api.finish({k: result[k] for k in ("resume", "ats", "review",
                                               "reached_target", "error")},
                       pdf_path=pdf, profile=prof)
    except Exception as exc:
        logger.exception("job %s failed", job["id"])
        api.finish({"failed": True, "error": str(exc)})


def serve(server: str | None = None, token: str | None = None, once: bool = False) -> None:
    cfg = load_config()
    server, token = server or cfg.get("server"), token or cfg.get("token")
    if not token:
        raise SystemExit("Not linked. Get a code on the website, then run: "
                         "python -m src.agent link CODE --server URL")
    engines = ",".join(installed_engines())
    print(f"Waiting for jobs from {server} (engines: {engines or 'none found'}). Ctrl+C to stop.")
    headers = {"Authorization": f"Bearer {token}"}

    def reset():
        try:
            requests.post(f"{server}/api/agent/reset", headers=headers, timeout=10)
        except requests.RequestException:
            pass

    reset()  # covers jobs left behind by a crash or a closed terminal
    try:
        _serve_loop(server, token, headers, engines, once)
    except KeyboardInterrupt:
        reset()
        print("\nStopped. Any job in progress is marked as failed on the website; submit it again.")


def _serve_loop(server: str, token: str, headers: dict, engines: str, once: bool) -> None:
    while True:
        try:
            r = requests.get(f"{server}/api/agent/next", params={"wait": 25, "engines": engines},
                             headers=headers, timeout=40)
        except requests.RequestException as exc:
            logger.warning("server unreachable (%s); retrying in 5s", exc)
            time.sleep(5)
            continue
        if r.status_code == 401:
            raise SystemExit("This computer was unlinked. Get a new code on the website.")
        job = r.json().get("job") if r.ok else None
        if job:
            print(f"job {job['id']} ({job['kind']}) started")
            handle_job(Api(server, token, job["id"]), job)
            print(f"job {job['id']} finished")
        if once:
            return
