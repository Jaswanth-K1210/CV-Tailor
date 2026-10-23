"""Terminal entry point: python -m src.agent {prompt,profile,run} ..."""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys

from src import ats_scorer, jd_fetcher, profile as profile_mod, tailor, tailor_loop
from src.file_extractor import extract_text
from src.llm import make_llm
from src.resume_pdf import render_pdf


_OPTIONAL_SECTIONS = ("missing section: summary", "missing section: certifications")


def local_ats(text: str, jd: str, profile_text: str | None = None) -> dict:
    # ponytail: local estimate until the ResumeWorded scraper lands (Plan 4).
    s = ats_scorer.score_cv(text, jd)
    # Only feed back things the writer can fix honestly: no optional sections it
    # would have to pad, and only missing keywords the profile actually backs.
    # (Scraped JDs include page chrome like "apple, search, submit, resume".)
    issues = [n for n in s["notes"]
              if not n.startswith("missing keywords") and n not in _OPTIONAL_SECTIONS]
    missing = s["missing_keywords"]
    if profile_text is not None:
        missing = [k for k in missing if k in profile_text]
    if missing:
        issues.append("missing keywords: " + ", ".join(missing[:15]))
    return {"score": round(s["score"]), "issues": issues}


def ask_in_terminal(questions: list[str]) -> dict[str, str]:
    print("\nThe job asks for things your profile doesn't show. Answer or press Enter to skip.")
    return {q: input(f"  {q}\n  > ") for q in questions}


def tailor_job(prof: dict, jd: str, engine: str, reviewer_engine: str | None,
               ask_gaps, on_round) -> dict:
    """Run the full loop with real engines. Mutates prof with gap answers."""
    writer = make_llm(engine)
    reviewer = make_llm(reviewer_engine or engine)
    return tailor_loop.run(
        prof, jd,
        write=lambda p, j, fb, prev: tailor.write_resume(p, j, writer, fb, prev),
        review=lambda p, j, cv, ats: tailor.review_resume(
            p, j, tailor.resume_to_text(cv), ats, reviewer),
        ats=lambda cv, j: local_ats(tailor.resume_to_text(cv), j, profile_mod.dumps(prof).lower()),
        ask_gaps=ask_gaps, on_round=on_round,
    )


def cmd_profile(a) -> None:
    sources = {"resume": extract_text(a.resume)}
    if a.github:
        sources["github"] = profile_mod.github_text(a.github)
    if a.linkedin:
        sources["linkedin"] = profile_mod.linkedin_text(a.linkedin)
    if a.ai_paste:
        with open(a.ai_paste, encoding="utf-8") as f:
            sources["ai_chat"] = f.read()
    p = profile_mod.build_profile(sources, make_llm(a.engine))
    with open(a.output, "w", encoding="utf-8") as f:
        f.write(profile_mod.dumps(p))
    print(f"profile saved to {a.output}: {len(p['experience'])} jobs, "
          f"{len(p['projects'])} projects")


def cmd_run(a) -> None:
    with open(a.profile, encoding="utf-8") as f:
        prof = json.load(f)
    if a.jd_file:
        with open(a.jd_file, encoding="utf-8") as f:
            jd = f.read()
    else:
        jd = jd_fetcher.fetch_jd(a.job)
    result = tailor_job(
        prof, jd, a.engine, a.reviewer_engine, ask_gaps=ask_in_terminal,
        on_round=lambda r: print(f"round {r['round']}: ATS {r['ats']['score']} · "
                                 f"review {r['review']['score']:g}/10"),
    )
    with open(a.profile, "w", encoding="utf-8") as f:
        f.write(profile_mod.dumps(prof))
    with open(a.output + ".rounds.json", "w", encoding="utf-8") as f:
        json.dump(result["rounds"], f, indent=2, ensure_ascii=False)
    render_pdf(result["resume"], a.output)
    if result["error"]:
        print(f"\nstopped early, {result['error']}")
    status = "target reached" if result["reached_target"] else "did not reach target"
    print(f"\n{status}: ATS {result['ats']['score']}, resume {result['review']['score']:g}/10, "
          f"job fit {result['review'].get('fit', 0):g}/10")
    for note in result["review"]["issues"]:
        print(f"  - {note}")
    print(f"PDF: {os.path.abspath(a.output)}")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="cv-tailor-agent")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("prompt", help="print the prompt to paste into your AI chat")

    p = sub.add_parser("profile", help="build your master profile")
    p.add_argument("--resume", required=True)
    p.add_argument("--github")
    p.add_argument("--linkedin", help="LinkedIn data export .zip")
    p.add_argument("--ai-paste", help="text file with your AI chat's answer to `prompt`")
    p.add_argument("--engine", default="claude")
    p.add_argument("-o", "--output", default="profile.json")

    r = sub.add_parser("run", help="tailor a resume to one job")
    r.add_argument("--profile", default="profile.json")
    src = r.add_mutually_exclusive_group(required=True)
    src.add_argument("--job", help="job posting URL")
    src.add_argument("--jd-file")
    r.add_argument("--engine", default="claude")
    r.add_argument("--reviewer-engine")
    r.add_argument("-o", "--output", default="resume.pdf")

    lk = sub.add_parser("link", help="link this computer to your account on the website")
    lk.add_argument("code")
    lk.add_argument("--server", required=True)
    sub.add_parser("serve", help="run jobs from the website on this computer")

    a = ap.parse_args(argv)
    if a.cmd in ("link", "serve"):
        from src import worker
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
        worker.link(a.server, a.code) if a.cmd == "link" else worker.serve()
    elif a.cmd == "prompt":
        print(profile_mod.AI_PASTE_PROMPT)
    elif a.cmd == "profile":
        cmd_profile(a)
    else:
        cmd_run(a)


if __name__ == "__main__":
    sys.exit(main())
