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


def test_write_prompt_contains_profile_and_no_invent_rule():
    llm = _capture("ASHA RAO\n...")
    out = tailor.write_resume(PROFILE, "JD TEXT", llm)
    assert out == "ASHA RAO\n..."
    assert "Kite" in llm.seen[0] and "JD TEXT" in llm.seen[0]
    assert "Never invent" in llm.seen[0]


def test_review_normalises_score_strings():
    for raw, want in (("9/10", 9.0), ("8.5", 8.5), (7, 7.0)):
        llm = _capture(json.dumps({"score": raw}))
        assert tailor.review_resume(PROFILE, "jd", "cv", {"score": 80}, llm)["score"] == want


def test_review_defaults_missing_lists_to_empty():
    r = tailor.review_resume(PROFILE, "jd", "cv", {"score": 80}, _capture('{"score": 9}'))
    assert r["issues"] == [] and r["fabrications"] == [] and r["missing_from_profile"] == []


def test_write_strips_preamble_fence_and_trailing_notes():
    raw = "HERE IS THE FINISHED CV:\n```\nASHA RAO\nEDUCATION\n```\n**Changes made:** | a | b |"
    assert tailor.write_resume(PROFILE, "jd", _capture(raw)) == "ASHA RAO\nEDUCATION"
