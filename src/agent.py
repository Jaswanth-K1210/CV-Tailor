"""Terminal entry point: python -m src.agent {prompt,profile,run} ..."""
from __future__ import annotations

import argparse
import json
import os
import sys

from src import ats_scorer, jd_fetcher, profile as profile_mod, sanitizer, tailor, tailor_loop
from src.file_extractor import extract_text
from src.llm import make_llm
from src.pdf_export import export_pdf


def local_ats(text: str, jd: str) -> dict:
    # ponytail: local estimate until the ResumeWorded scraper lands (Plan 4).
    s = ats_scorer.score_cv(text, jd)
    issues = list(s["notes"])
    if s["missing_keywords"]:
        issues.append("missing keywords: " + ", ".join(s["missing_keywords"][:15]))
    return {"score": round(s["score"]), "issues": issues}


def ask_in_terminal(questions: list[str]) -> dict[str, str]:
    print("\nThe job asks for things your profile doesn't show. Answer or press Enter to skip.")
    return {q: input(f"  {q}\n  > ") for q in questions}


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
    writer = make_llm(a.engine)
    reviewer = make_llm(a.reviewer_engine or a.engine)

    result = tailor_loop.run(
        prof, jd,
        write=lambda p, j, fb, prev: sanitizer.remove_dashes(
            tailor.write_resume(p, j, writer, fb, prev)),
        review=lambda p, j, cv, ats: tailor.review_resume(p, j, cv, ats, reviewer),
        ats=local_ats,
        ask_gaps=ask_in_terminal,
        on_round=lambda r: print(f"round {r['round']}: ATS {r['ats']['score']} · "
                                 f"review {r['review']['score']:g}/10"),
    )
    with open(a.profile, "w", encoding="utf-8") as f:
        f.write(profile_mod.dumps(prof))
    with open(a.output + ".rounds.json", "w", encoding="utf-8") as f:
        json.dump(result["rounds"], f, indent=2, ensure_ascii=False)
    export_pdf(result["resume"], a.output)
    if result["error"]:
        print(f"\nstopped early, {result['error']}")
    status = "target reached" if result["reached_target"] else "did not reach target"
    print(f"\n{status}: ATS {result['ats']['score']}, review {result['review']['score']:g}/10")
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

    a = ap.parse_args(argv)
    if a.cmd == "prompt":
        print(profile_mod.AI_PASTE_PROMPT)
    elif a.cmd == "profile":
        cmd_profile(a)
    else:
        cmd_run(a)


if __name__ == "__main__":
    sys.exit(main())
