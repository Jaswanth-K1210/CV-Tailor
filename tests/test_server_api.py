import io
import json
import time

import pytest
from fastapi.testclient import TestClient

from server.app import create_app


@pytest.fixture
def make_client(tmp_path, monkeypatch):
    monkeypatch.setenv("CVT_DEV_LOGIN", "1")
    app = create_app(str(tmp_path))

    def make(email=None):
        c = TestClient(app)
        if email:
            assert c.post("/api/auth/dev", json={"email": email}).status_code == 200
        return c
    make.data_dir = tmp_path
    return make


def _with_profile(c):
    c.put("/api/profile", json={"profile": {"contact": {"name": "A"}}})
    return c


def _link(c, engines=("claude",)):
    code = c.post("/api/devices/code").json()["code"]
    token = c.post("/api/agent/link", json={"code": code, "engines": list(engines)}).json()["token"]
    return {"Authorization": f"Bearer {token}"}


# ---------- auth / user ----------

def test_dev_login_sets_cookie_and_me_works(make_client):
    c = make_client("a@x.com")
    me = c.get("/api/me").json()
    assert me["email"] == "a@x.com" and me["has_profile"] is False


def test_dev_login_disabled_without_env(make_client, monkeypatch):
    monkeypatch.delenv("CVT_DEV_LOGIN")
    assert make_client().post("/api/auth/dev", json={"email": "a@x.com"}).status_code == 404


def test_me_requires_login(make_client):
    assert make_client().get("/api/me").status_code == 401


def test_google_login_rejects_wrong_aud(make_client, monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "mine")

    class R:
        ok = True

        def json(self):
            return {"aud": "someone-else", "email": "a@x.com", "email_verified": "true"}

    monkeypatch.setattr("server.app.requests.get", lambda *a, **k: R())
    assert make_client().post("/api/auth/google", json={"credential": "t"}).status_code == 401


def test_other_users_job_is_404(make_client):
    a = _with_profile(make_client("a@x.com"))
    jid = a.post("/api/jobs", json={"jd": "Python dev"}).json()["id"]
    b = make_client("b@x.com")
    assert b.get(f"/api/jobs/{jid}").status_code == 404
    assert b.get(f"/api/jobs/{jid}/pdf").status_code == 404
    assert b.post(f"/api/jobs/{jid}/answers", json={}).status_code == 404


def test_job_needs_profile_and_input(make_client):
    c = make_client("a@x.com")
    assert c.post("/api/jobs", json={"jd": "x"}).status_code == 400
    _with_profile(c)
    assert c.post("/api/jobs", json={}).status_code == 400


def test_job_rate_limit_20_per_day(make_client):
    c = _with_profile(make_client("a@x.com"))
    for _ in range(20):
        assert c.post("/api/jobs", json={"jd": "x"}).status_code == 200
    assert c.post("/api/jobs", json={"jd": "x"}).status_code == 429


def test_delete_me_removes_pdf_file(make_client):
    c = _with_profile(make_client("a@x.com"))
    headers = _link(c)
    jid = c.post("/api/jobs", json={"jd": "x"}).json()["id"]
    c.get("/api/agent/next?wait=0", headers=headers)
    c.post(f"/api/agent/jobs/{jid}/finish", headers=headers,
           data={"result": json.dumps({"resume": "cv"})},
           files={"pdf": ("r.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")})
    pdf = make_client.data_dir / "pdfs" / f"{jid}.pdf"
    assert pdf.exists()
    assert c.delete("/api/me").status_code == 200
    assert not pdf.exists()
    assert c.get("/api/me").status_code == 401


def test_profile_sources_queue_profile_job(make_client):
    c = make_client("a@x.com")
    r = c.post("/api/profile/sources",
               files={"resume": ("cv.txt", io.BytesIO(b"Asha Rao, Python dev"), "text/plain")},
               data={"github": "asha", "ai_paste": "Built Kite"})
    assert r.status_code == 200
    headers = _link(c)
    job = c.get("/api/agent/next?wait=0", headers=headers).json()["job"]
    assert job["kind"] == "profile"
    assert job["sources"] == {"resume": "Asha Rao, Python dev", "ai_chat": "Built Kite",
                              "github_user": "asha"}


# ---------- agent ----------

def test_link_with_code_once(make_client):
    c = make_client("a@x.com")
    code = c.post("/api/devices/code").json()["code"]
    assert c.post("/api/agent/link", json={"code": code}).status_code == 200
    assert c.post("/api/agent/link", json={"code": code}).status_code == 400


def test_expired_code_rejected(make_client, monkeypatch):
    c = make_client("a@x.com")
    code = c.post("/api/devices/code").json()["code"]
    real = time.time
    monkeypatch.setattr("server.app.time.time", lambda: real() + 601)
    assert c.post("/api/agent/link", json={"code": code}).status_code == 400


def test_claim_is_exclusive(make_client):
    c = _with_profile(make_client("a@x.com"))
    h1, h2 = _link(c), _link(c)
    c.post("/api/jobs", json={"jd": "x"})
    first = c.get("/api/agent/next?wait=0", headers=h1).json()["job"]
    second = c.get("/api/agent/next?wait=0", headers=h2).json()["job"]
    assert first is not None and second is None


def test_poll_updates_last_seen_and_engines(make_client):
    c = make_client("a@x.com")
    headers = _link(c, engines=["claude"])
    c.get("/api/agent/next?wait=0&engines=claude,agy", headers=headers)
    dev = c.get("/api/me").json()["devices"][0]
    assert dev["engines"] == ["claude", "agy"]
    assert time.time() - dev["last_seen"] < 5


def test_agent_cannot_touch_other_users_job(make_client):
    a = _with_profile(make_client("a@x.com"))
    jid = a.post("/api/jobs", json={"jd": "x"}).json()["id"]
    b_headers = _link(make_client("b@x.com"))
    assert b_headers and make_client().post(
        f"/api/agent/jobs/{jid}/event", json={"type": "log"}, headers=b_headers).status_code == 404


def test_unknown_device_rejected(make_client):
    r = make_client().get("/api/agent/next?wait=0", headers={"Authorization": "Bearer nope"})
    assert r.status_code == 401


def test_questions_answers_roundtrip(make_client):
    c = _with_profile(make_client("a@x.com"))
    headers = _link(c)
    jid = c.post("/api/jobs", json={"jd": "x"}).json()["id"]
    c.get("/api/agent/next?wait=0", headers=headers)
    ids = c.post(f"/api/agent/jobs/{jid}/questions", headers=headers,
                 json={"questions": ["Django?", "AWS?"],
                       "drafts": {"Django?": "Built a blog in Django"}}).json()["ids"]
    qs = c.get(f"/api/jobs/{jid}").json()["questions"]
    assert qs[0]["draft"] == "Built a blog in Django" and qs[1]["draft"] is None
    assert c.get(f"/api/jobs/{jid}").json()["status"] == "waiting"
    c.post(f"/api/jobs/{jid}/answers", json={str(ids[0]): "Yes, at Acme"})
    got = c.get(f"/api/agent/jobs/{jid}/answers", headers=headers).json()
    assert got == {"answers": {"Django?": "Yes, at Acme"}, "pending": 1}
    assert c.get(f"/api/jobs/{jid}").json()["status"] == "waiting"
    c.post(f"/api/jobs/{jid}/answers", json={str(ids[1]): ""})
    job = c.get(f"/api/jobs/{jid}").json()
    assert job["status"] == "running"
    assert job["events"][-1]["data"]["msg"].startswith("Got your answers")


def test_finish_stores_pdf_and_profile(make_client):
    c = _with_profile(make_client("a@x.com"))
    headers = _link(c)
    jid = c.post("/api/jobs", json={"jd": "x"}).json()["id"]
    c.get("/api/agent/next?wait=0", headers=headers)
    c.post(f"/api/agent/jobs/{jid}/event", headers=headers,
           json={"type": "round", "data": {"round": 1, "ats": {"score": 80}}})
    c.post(f"/api/agent/jobs/{jid}/finish", headers=headers,
           data={"result": json.dumps({"ats": {"score": 90}, "review": {"score": 9}}),
                 "profile": json.dumps({"contact": {"name": "B"}})},
           files={"pdf": ("r.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")})
    job = c.get(f"/api/jobs/{jid}").json()
    assert job["status"] == "done" and job["has_pdf"] and job["events"][0]["type"] == "round"
    assert c.get(f"/api/jobs/{jid}/pdf").content == b"%PDF-1.4"
    assert c.get("/api/profile").json()["profile"] == {"contact": {"name": "B"}}
    assert c.get("/api/jobs").json()["jobs"][0]["review"] == 9


def test_agent_reset_fails_unfinished_jobs(make_client):
    c = _with_profile(make_client("a@x.com"))
    headers = _link(c)
    running = c.post("/api/jobs", json={"jd": "x"}).json()["id"]
    c.get("/api/agent/next?wait=0", headers=headers)
    queued = c.post("/api/jobs", json={"jd": "y"}).json()["id"]
    assert c.post("/api/agent/reset", headers=headers).status_code == 200
    job = c.get(f"/api/jobs/{running}").json()
    assert job["status"] == "failed" and "restarted" in job["error"]
    assert c.get(f"/api/jobs/{queued}").json()["status"] == "queued"
