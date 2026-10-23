import csv
import io
import json
import zipfile

from src import profile, tailor

PROFILE = {"contact": {"name": "Asha Rao"}, "projects": [{"name": "Kite", "source": "github"}]}


def _capture(reply):
    seen = []

    def llm(prompt):
        seen.append(prompt)
        return reply
    llm.seen = seen
    return llm


def test_linkedin_text_reads_positions(tmp_path):
    buf = io.StringIO()
    csv.writer(buf).writerows([["Company Name", "Title"], ["Acme", "SDE Intern"]])
    z = tmp_path / "li.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("Positions.csv", buf.getvalue())
    text = profile.linkedin_text(str(z))
    assert "Acme" in text and "SDE Intern" in text


def test_build_profile_returns_schema_keys():
    llm = _capture(json.dumps({"contact": {"name": "Asha"}, "projects": [{"name": "Kite"}]}))
    p = profile.build_profile({"resume": "Asha ... Kite"}, llm)
    for key in ("contact", "education", "experience", "projects", "skills",
                "achievements", "certifications"):
        assert key in p
    assert p["projects"][0]["source"] == "unknown"
    assert "Asha ... Kite" in llm.seen[0]


RESUME = {"name": "Asha Rao",
          "contact": {"email": "asha@x.com", "github": "github.com/asha-rao"},
          "experience": [{"title": "SDE Intern", "company": "Acme", "dates": "2024 - 2025",
                          "bullets": ["Built a full-stack app"]}],
          "projects": [{"name": "Kite", "tech": ["Python"], "link": "https://kite-app.dev",
                        "bullets": ["Scheduled 1,000 jobs"]}],
          "skills": [{"category": "Languages", "items": ["Python"]}]}


def test_write_prompt_contains_profile_and_no_invent_rule():
    llm = _capture("Here you go:\n```json\n" + json.dumps(RESUME) + "\n```")
    out = tailor.write_resume(PROFILE, "JD TEXT", llm)
    assert out["name"] == "Asha Rao"
    assert "Kite" in llm.seen[0] and "JD TEXT" in llm.seen[0]
    assert "Never invent" in llm.seen[0]


def test_write_removes_dashes_from_text_but_not_links():
    out = tailor.write_resume(PROFILE, "jd", _capture(json.dumps(RESUME)))
    assert out["contact"]["github"] == "github.com/asha-rao"
    assert out["experience"][0]["dates"] == "2024 to 2025"
    assert out["experience"][0]["bullets"] == ["Built a full stack app"]
    assert out["projects"][0]["link"] == "https://kite-app.dev"


def test_resume_to_text_has_sections_and_bullets():
    text = tailor.resume_to_text(RESUME)
    assert text.startswith("Asha Rao\nasha@x.com | github.com/asha-rao")
    for part in ("EXPERIENCE", "PROJECTS", "TECHNICAL SKILLS", "  • Built a full-stack app",
                 "Languages: Python"):
        assert part in text


def test_review_normalises_score_strings():
    for raw, want in (("9/10", 9.0), ("8.5", 8.5), (7, 7.0)):
        llm = _capture(json.dumps({"score": raw, "fit": "4/10"}))
        r = tailor.review_resume(PROFILE, "jd", "cv", {"score": 80}, llm)
        assert r["score"] == want and r["fit"] == 4.0


def test_review_defaults_missing_lists_to_empty():
    r = tailor.review_resume(PROFILE, "jd", "cv", {"score": 80}, _capture('{"score": 9}'))
    assert r["issues"] == [] and r["fabrications"] == [] and r["missing_from_profile"] == []


def test_github_text_accepts_url_and_handle(monkeypatch):
    urls = []

    class R:
        def raise_for_status(self):
            pass

        def json(self):
            return []

    monkeypatch.setattr(profile.requests, "get", lambda url, **k: urls.append(url) or R())
    for given in ("https://github.com/Jaswanth-K1210", "github.com/Jaswanth-K1210/",
                  "@Jaswanth-K1210", "Jaswanth-K1210"):
        profile.github_text(given)
    assert set(urls) == {"https://api.github.com/users/Jaswanth-K1210/repos"}


def test_review_prompt_lists_requested_fixes():
    llm = _capture('{"score": 9}')
    tailor.review_resume(PROFILE, "jd", "cv", {"score": 80}, llm, requested="Reviewer: cut X")
    assert "FIXES REQUESTED IN THE LAST REVIEW" in llm.seen[0] and "cut X" in llm.seen[0]
