import json

from src import agent

CV = """ASHA RAO
asha@x.com | 9999999999 | linkedin.com/in/asha | github.com/asha

EDUCATION
IIT Madras  2020 to 2024
  B.Tech Computer Science

PROJECTS
Kite  2023
  • Built a Python scheduler serving 1,000 users
"""


def test_agent_run_with_fakes(tmp_path, monkeypatch):
    prof = tmp_path / "profile.json"
    prof.write_text(json.dumps({"contact": {"name": "Asha Rao"}, "projects": []}))
    jd = tmp_path / "jd.txt"
    jd.write_text("Python developer with Kubernetes")

    def fake_make_llm(engine, model=None, timeout=300):
        def llm(prompt):
            if "hiring manager" in prompt:
                return json.dumps({"score": 9, "missing_from_profile": ["Used Kubernetes?"]})
            return CV
        return llm

    monkeypatch.setattr(agent, "make_llm", fake_make_llm)
    monkeypatch.setattr(agent, "local_ats", lambda text, jd: {"score": 90, "issues": []})
    monkeypatch.setattr("builtins.input", lambda _: "")
    out = tmp_path / "out.pdf"
    agent.main(["run", "--profile", str(prof), "--jd-file", str(jd), "-o", str(out)])
    assert out.stat().st_size > 0
    assert json.loads(prof.read_text())["contact"]["name"] == "Asha Rao"


def test_local_ats_reports_missing_keywords():
    r = agent.local_ats(CV, "Kubernetes Kubernetes Terraform Terraform Python")
    assert isinstance(r["score"], int)
    assert any("missing keywords" in i for i in r["issues"])
