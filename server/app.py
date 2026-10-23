from __future__ import annotations

import asyncio
import hashlib
import json
import os
import secrets
import shutil
import tempfile
import time

import requests
from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse

from server import db

COOKIE = "cvt_session"
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
JOBS_PER_DAY = 20
STATIC = os.path.join(os.path.dirname(__file__), "static")


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _loads(s, default=None):
    return json.loads(s) if s else default


def create_app(data_dir: str) -> FastAPI:
    os.makedirs(os.path.join(data_dir, "pdfs"), exist_ok=True)
    conn = db.connect(os.path.join(data_dir, "cvt.db"))
    pdf_dir = os.path.join(data_dir, "pdfs")
    app = FastAPI()
    # All endpoints are async, so they run one at a time on the event loop and
    # share this one connection without locking.

    # ---------- helpers ----------

    def q(sql, *args):
        return conn.execute(sql, args)

    def user_from_session(request: Request):
        token = request.cookies.get(COOKIE)
        row = token and q("SELECT u.* FROM sessions s JOIN users u ON u.id = s.user_id "
                          "WHERE s.token = ?", token).fetchone()
        if not row:
            raise HTTPException(401, "not signed in")
        return row

    def device_from_bearer(request: Request):
        auth = request.headers.get("authorization", "")
        token = auth.removeprefix("Bearer ").strip()
        row = token and q("SELECT * FROM devices WHERE token_hash = ?", _hash(token)).fetchone()
        if not row:
            raise HTTPException(401, "unknown device")
        return row

    def own_job(job_id: int, user_id: int):
        row = q("SELECT * FROM jobs WHERE id = ? AND user_id = ?", job_id, user_id).fetchone()
        if not row:
            raise HTTPException(404, "job not found")
        return row

    def start_session(response: Response, email: str, name: str = ""):
        q("INSERT INTO users(email, name, created_at) VALUES (?, ?, ?) "
          "ON CONFLICT(email) DO UPDATE SET name = COALESCE(NULLIF(excluded.name, ''), name)",
          email.lower(), name, time.time())
        uid = q("SELECT id FROM users WHERE email = ?", email.lower()).fetchone()["id"]
        token = secrets.token_urlsafe(32)
        q("INSERT INTO sessions(token, user_id, created_at) VALUES (?, ?, ?)", token, uid, time.time())
        response.set_cookie(COOKIE, token, httponly=True, samesite="lax",
                            secure=os.environ.get("CVT_SECURE_COOKIES") == "1",
                            max_age=60 * 60 * 24 * 30)
        return {"ok": True}

    def add_event(job_id, type_, data):
        q("INSERT INTO events(job_id, ts, type, data_json) VALUES (?, ?, ?, ?)",
          job_id, time.time(), type_, json.dumps(data))
        q("UPDATE jobs SET updated_at = ? WHERE id = ?", time.time(), job_id)

    def queue_job(user_id, kind, job_url=None, jd=None):
        since = time.time() - 86400
        n = q("SELECT COUNT(*) FROM jobs WHERE user_id = ? AND kind = 'tailor' AND created_at > ?",
              user_id, since).fetchone()[0]
        if kind == "tailor" and n >= JOBS_PER_DAY:
            raise HTTPException(429, f"limit is {JOBS_PER_DAY} resumes per day")
        now = time.time()
        return q("INSERT INTO jobs(user_id, kind, job_url, jd, created_at, updated_at) "
                 "VALUES (?, ?, ?, ?, ?, ?)", user_id, kind, job_url, jd, now, now).lastrowid

    # ---------- auth ----------

    @app.post("/api/auth/google")
    async def auth_google(body: dict, response: Response):
        client_id = os.environ.get("GOOGLE_CLIENT_ID")
        if not client_id:
            raise HTTPException(500, "GOOGLE_CLIENT_ID not configured")
        r = await run_in_threadpool(
            requests.get, "https://oauth2.googleapis.com/tokeninfo",
            params={"id_token": body.get("credential", "")}, timeout=10)
        info = r.json() if r.ok else {}
        if info.get("aud") != client_id or info.get("email_verified") not in ("true", True):
            raise HTTPException(401, "invalid Google sign-in")
        return start_session(response, info["email"], info.get("name", ""))

    @app.post("/api/auth/dev")
    async def auth_dev(body: dict, response: Response):
        if os.environ.get("CVT_DEV_LOGIN") != "1":
            raise HTTPException(404)
        return start_session(response, body["email"], body.get("name", ""))

    @app.post("/api/auth/logout")
    async def logout(request: Request, response: Response):
        q("DELETE FROM sessions WHERE token = ?", request.cookies.get(COOKIE, ""))
        response.delete_cookie(COOKIE)
        return {"ok": True}

    @app.get("/api/config")
    async def config():
        from src.profile import AI_PASTE_PROMPT
        return {"ai_prompt": AI_PASTE_PROMPT,
                "google_client_id": os.environ.get("GOOGLE_CLIENT_ID", ""),
                "dev_login": os.environ.get("CVT_DEV_LOGIN") == "1"}

    # ---------- user ----------

    @app.get("/api/me")
    async def me(user=Depends(user_from_session)):
        devices = [{"id": d["id"], "engines": _loads(d["engines_json"], []),
                    "last_seen": d["last_seen"]}
                   for d in q("SELECT * FROM devices WHERE user_id = ?", user["id"])]
        return {"email": user["email"], "name": user["name"], "engine": user["engine"],
                "has_profile": bool(user["profile_json"]), "devices": devices,
                "telegram": False, "now": time.time()}

    @app.put("/api/me")
    async def update_me(body: dict, user=Depends(user_from_session)):
        if body.get("engine") not in ("claude", "codex", "agy"):
            raise HTTPException(400, "engine must be claude, codex or agy")
        q("UPDATE users SET engine = ? WHERE id = ?", body["engine"], user["id"])
        return {"ok": True}

    @app.delete("/api/me")
    async def delete_me(response: Response, user=Depends(user_from_session)):
        for (jid,) in q("SELECT id FROM jobs WHERE user_id = ?", user["id"]).fetchall():
            path = os.path.join(pdf_dir, f"{jid}.pdf")
            if os.path.exists(path):
                os.remove(path)
        q("DELETE FROM users WHERE id = ?", user["id"])
        response.delete_cookie(COOKIE)
        return {"ok": True}

    # ---------- profile ----------

    @app.get("/api/profile")
    async def get_profile(user=Depends(user_from_session)):
        return {"profile": _loads(user["profile_json"]),
                "sources": list(_loads(user["sources_json"], {}).keys())}

    @app.put("/api/profile")
    async def put_profile(body: dict, user=Depends(user_from_session)):
        if not isinstance(body.get("profile"), dict):
            raise HTTPException(400, "profile must be a JSON object")
        q("UPDATE users SET profile_json = ? WHERE id = ?", json.dumps(body["profile"]), user["id"])
        return {"ok": True}

    @app.post("/api/profile/sources")
    async def profile_sources(resume: UploadFile = File(...),
                              linkedin: UploadFile | None = File(None),
                              github: str = Form(""), ai_paste: str = Form(""),
                              user=Depends(user_from_session)):
        from src.file_extractor import ExtractError, extract_text
        from src.profile import linkedin_text

        sources = {}
        with tempfile.TemporaryDirectory() as tmp:
            for up, key in ((resume, "resume"), (linkedin, "linkedin")):
                if not up or not up.filename:
                    continue
                path = os.path.join(tmp, os.path.basename(up.filename))
                with open(path, "wb") as f:
                    shutil.copyfileobj(up.file, f)
                try:
                    sources[key] = linkedin_text(path) if key == "linkedin" else extract_text(path)
                except (ExtractError, Exception) as exc:
                    raise HTTPException(400, f"could not read {key}: {exc}")
        if ai_paste.strip():
            sources["ai_chat"] = ai_paste.strip()
        if github.strip():
            sources["github_user"] = github.strip()
        q("UPDATE users SET sources_json = ? WHERE id = ?", json.dumps(sources), user["id"])
        return {"id": queue_job(user["id"], "profile")}

    # ---------- jobs (site) ----------

    @app.post("/api/jobs")
    async def create_job(body: dict, user=Depends(user_from_session)):
        url, jd = (body.get("job_url") or "").strip(), (body.get("jd") or "").strip()
        if not url and not jd:
            raise HTTPException(400, "give a job link or paste the job description")
        if not user["profile_json"]:
            raise HTTPException(400, "build your profile first")
        return {"id": queue_job(user["id"], "tailor", url or None, jd or None)}

    @app.get("/api/jobs")
    async def list_jobs(user=Depends(user_from_session)):
        rows = q("SELECT id, kind, status, job_url, result_json, error, created_at FROM jobs "
                 "WHERE user_id = ? ORDER BY id DESC LIMIT 100", user["id"]).fetchall()
        out = []
        for r in rows:
            res = _loads(r["result_json"], {})
            out.append({"id": r["id"], "kind": r["kind"], "status": r["status"],
                        "job_url": r["job_url"], "error": r["error"], "created_at": r["created_at"],
                        "ats": (res.get("ats") or {}).get("score"),
                        "review": (res.get("review") or {}).get("score")})
        return {"jobs": out}

    @app.get("/api/jobs/{job_id}")
    async def get_job(job_id: int, user=Depends(user_from_session)):
        j = own_job(job_id, user["id"])
        events = [{"ts": e["ts"], "type": e["type"], "data": _loads(e["data_json"])}
                  for e in q("SELECT * FROM events WHERE job_id = ? ORDER BY id", job_id)]
        questions = [dict(r) for r in q("SELECT id, text, draft, answer FROM questions "
                                        "WHERE job_id = ?", job_id)]
        return {"id": j["id"], "kind": j["kind"], "status": j["status"], "job_url": j["job_url"],
                "jd": j["jd"], "error": j["error"], "result": _loads(j["result_json"]),
                "events": events, "questions": questions,
                "has_pdf": os.path.exists(os.path.join(pdf_dir, f"{job_id}.pdf"))}

    @app.post("/api/jobs/{job_id}/answers")
    async def answer(job_id: int, body: dict, user=Depends(user_from_session)):
        own_job(job_id, user["id"])
        for qid, text in body.items():
            q("UPDATE questions SET answer = ?, answered_at = ? WHERE id = ? AND job_id = ?",
              str(text), time.time(), int(qid), job_id)
        return {"ok": True}

    @app.get("/api/jobs/{job_id}/pdf")
    async def job_pdf(job_id: int, user=Depends(user_from_session)):
        own_job(job_id, user["id"])
        path = os.path.join(pdf_dir, f"{job_id}.pdf")
        if not os.path.exists(path):
            raise HTTPException(404, "no PDF yet")
        return FileResponse(path, media_type="application/pdf", filename=f"resume_{job_id}.pdf")

    # ---------- helper pairing + agent API ----------

    @app.post("/api/devices/code")
    async def pair_code(user=Depends(user_from_session)):
        code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(6))
        q("INSERT INTO pair_codes(code, user_id, expires_at) VALUES (?, ?, ?)",
          code, user["id"], time.time() + 600)
        return {"code": code, "expires_in": 600}

    @app.post("/api/agent/link")
    async def agent_link(body: dict):
        code = (body.get("code") or "").strip().upper()
        row = q("SELECT * FROM pair_codes WHERE code = ?", code).fetchone()
        if not row or row["used"] or row["expires_at"] < time.time():
            raise HTTPException(400, "code is invalid or expired; get a new one on the site")
        q("UPDATE pair_codes SET used = 1 WHERE code = ?", code)
        token = secrets.token_urlsafe(32)
        q("INSERT INTO devices(user_id, token_hash, engines_json, last_seen) VALUES (?, ?, ?, ?)",
          row["user_id"], _hash(token), json.dumps(body.get("engines") or []), time.time())
        return {"token": token}

    @app.get("/api/agent/next")
    async def agent_next(wait: float = 25, engines: str = "", dev=Depends(device_from_bearer)):
        deadline = time.time() + min(wait, 25)
        if engines:
            q("UPDATE devices SET engines_json = ? WHERE id = ?",
              json.dumps(engines.split(",")), dev["id"])
        while True:
            q("UPDATE devices SET last_seen = ? WHERE id = ?", time.time(), dev["id"])
            row = q("SELECT * FROM jobs WHERE user_id = ? AND status = 'queued' ORDER BY id LIMIT 1",
                    dev["user_id"]).fetchone()
            if row and q("UPDATE jobs SET status = 'running', updated_at = ? "
                         "WHERE id = ? AND status = 'queued'", time.time(), row["id"]).rowcount:
                user = q("SELECT * FROM users WHERE id = ?", dev["user_id"]).fetchone()
                return {"job": {"id": row["id"], "kind": row["kind"], "job_url": row["job_url"],
                                "jd": row["jd"], "engine": user["engine"],
                                "profile": _loads(user["profile_json"]),
                                "sources": _loads(user["sources_json"], {})}}
            if time.time() >= deadline:
                return {"job": None}
            await asyncio.sleep(1)

    @app.post("/api/agent/reset")
    async def agent_reset(dev=Depends(device_from_bearer)):
        # The helper calls this on start: anything it was running died with it.
        # ponytail: fails all of the user's unfinished jobs, so with two linked
        # computers a restart on one also fails the other's job; track the
        # claiming device per job if multi-computer use becomes common.
        q("UPDATE jobs SET status = 'failed', updated_at = ?, error = ? "
          "WHERE user_id = ? AND status IN ('running', 'waiting')", time.time(),
          "The helper on your computer was restarted before this finished. Submit the job again.",
          dev["user_id"])
        return {"ok": True}

    def agent_job(job_id: int, dev):
        row = q("SELECT * FROM jobs WHERE id = ? AND user_id = ?", job_id, dev["user_id"]).fetchone()
        if not row:
            raise HTTPException(404, "job not found")
        return row

    @app.post("/api/agent/jobs/{job_id}/event")
    async def agent_event(job_id: int, body: dict, dev=Depends(device_from_bearer)):
        agent_job(job_id, dev)
        if body.get("type") == "jd":
            q("UPDATE jobs SET jd = ? WHERE id = ?", (body.get("data") or {}).get("jd"), job_id)
        q("UPDATE jobs SET status = 'running' WHERE id = ? AND status = 'waiting'", job_id)
        add_event(job_id, body.get("type", "log"), body.get("data"))
        return {"ok": True}

    @app.post("/api/agent/jobs/{job_id}/questions")
    async def agent_questions(job_id: int, body: dict, dev=Depends(device_from_bearer)):
        agent_job(job_id, dev)
        drafts = body.get("drafts") or {}
        ids = [q("INSERT INTO questions(job_id, text, draft, asked_at) VALUES (?, ?, ?, ?)",
                 job_id, text, drafts.get(text) or None, time.time()).lastrowid
               for text in body.get("questions", [])]
        q("UPDATE jobs SET status = 'waiting', updated_at = ? WHERE id = ?", time.time(), job_id)
        return {"ids": ids}

    @app.get("/api/agent/jobs/{job_id}/answers")
    async def agent_answers(job_id: int, dev=Depends(device_from_bearer)):
        agent_job(job_id, dev)
        rows = q("SELECT text, answer FROM questions WHERE job_id = ?", job_id).fetchall()
        return {"answers": {r["text"]: r["answer"] for r in rows if r["answer"] is not None},
                "pending": sum(r["answer"] is None for r in rows)}

    @app.post("/api/agent/jobs/{job_id}/finish")
    async def agent_finish(job_id: int, result: str = Form(...),
                           pdf: UploadFile | None = File(None), profile: str = Form(""),
                           dev=Depends(device_from_bearer)):
        agent_job(job_id, dev)
        res = json.loads(result)
        if pdf and pdf.filename:
            with open(os.path.join(pdf_dir, f"{job_id}.pdf"), "wb") as f:
                shutil.copyfileobj(pdf.file, f)
        if profile:
            q("UPDATE users SET profile_json = ? WHERE id = ?", profile, dev["user_id"])
        q("UPDATE jobs SET status = ?, result_json = ?, error = ?, updated_at = ? WHERE id = ?",
          "failed" if res.get("failed") else "done", result, res.get("error"), time.time(), job_id)
        q("UPDATE questions SET answer = '' WHERE job_id = ? AND answer IS NULL", job_id)
        return {"ok": True}

    # ---------- site ----------

    @app.get("/")
    async def index():
        return FileResponse(os.path.join(STATIC, "index.html"))

    @app.get("/static/{name}")
    async def static(name: str):
        path = os.path.join(STATIC, os.path.basename(name))
        if not os.path.exists(path):
            raise HTTPException(404)
        return FileResponse(path)

    return app
