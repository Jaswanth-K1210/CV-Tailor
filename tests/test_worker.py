import json

from src import agent, worker


class FakeApi:
    def __init__(self, answers=None):
        self.events, self.finished, self.asked = [], None, []
        self.answers = answers or {}

    def event(self, type_, data):
        self.events.append((type_, data))

    def ask(self, questions):
        self.asked.extend(questions)
        return self.answers

    def finish(self, result, pdf_path=None, profile=None):
        import os
        self.finished = {"result": result, "pdf_ok": bool(pdf_path and os.path.getsize(pdf_path)),
                         "profile": profile}


CV = "ASHA RAO\nasha@x.com\n\nPROJECTS\nKite  2023\n  • Built a scheduler\n"


def _fake_llm(engine, model=None, timeout=300):
    def llm(prompt):
        if "hiring manager" in prompt:
            return json.dumps({"score": 9})
        if "master profile" in prompt:
            return json.dumps({"contact": {"name": "Asha"}})
        return CV
    return llm


def test_handle_tailor_job_reports_rounds_and_finishes(monkeypatch):
    monkeypatch.setattr(agent, "make_llm", _fake_llm)
    monkeypatch.setattr(agent, "local_ats", lambda t, j: {"score": 90, "issues": []})
    api = FakeApi()
    worker.handle_job(api, {"id": 1, "kind": "tailor", "jd": "Python dev", "job_url": None,
                            "engine": "claude", "profile": {"contact": {"name": "Asha"}}})
    assert [t for t, _ in api.events] == ["round"]
    assert api.finished["pdf_ok"] and api.finished["result"]["reached_target"] is True
    assert api.finished["profile"] == {"contact": {"name": "Asha"}}


def test_handle_profile_job_expands_github(monkeypatch):
    monkeypatch.setattr(agent, "make_llm", _fake_llm)
    monkeypatch.setattr(worker.profile_mod, "github_text", lambda u: f"repos of {u}")
    seen = {}
    real = worker.profile_mod.build_profile

    def spy(sources, llm):
        seen.update(sources)
        return real(sources, llm)

    monkeypatch.setattr(worker.profile_mod, "build_profile", spy)
    api = FakeApi()
    worker.handle_job(api, {"id": 2, "kind": "profile", "engine": "claude",
                            "sources": {"resume": "cv", "github_user": "asha"}})
    assert seen == {"resume": "cv", "github": "repos of asha"}
    assert api.finished["profile"]["contact"] == {"name": "Asha"}


def test_handle_job_failure_reports_error(monkeypatch):
    def boom(url):
        raise RuntimeError("page blocked")
    monkeypatch.setattr(worker.jd_fetcher, "fetch_jd", boom)
    api = FakeApi()
    worker.handle_job(api, {"id": 3, "kind": "tailor", "jd": None, "job_url": "https://x",
                            "engine": "claude", "profile": {}})
    assert api.finished["result"] == {"failed": True, "error": "page blocked"}


def test_ask_returns_partial_answers_after_timeout(monkeypatch):
    class R:
        def __init__(self, body):
            self.body = body

        def json(self):
            return self.body

        def raise_for_status(self):
            pass

    monkeypatch.setattr(worker.requests, "post", lambda *a, **k: R({"ids": [1]}))
    monkeypatch.setattr(worker.requests, "get",
                        lambda *a, **k: R({"answers": {}, "pending": 1}))
    api = worker.Api("http://s", "t", 1)
    assert api.ask(["Django?"], timeout=0, poll=0) == {}
