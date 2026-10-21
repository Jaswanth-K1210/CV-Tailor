from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

ATS_TARGET = 85      # must be strictly above
REVIEW_TARGET = 9    # must be at least


def _passes(rnd: dict) -> bool:
    return (rnd["ats"]["score"] > ATS_TARGET
            and rnd["review"]["score"] >= REVIEW_TARGET
            and not rnd["review"]["fabrications"])


def _rank(rnd: dict) -> tuple:
    return (_passes(rnd), rnd["review"]["score"] + rnd["ats"]["score"] / 10)


def run(profile: dict, jd: str, *, write, review, ats, ask_gaps,
        on_round=lambda r: None, max_rounds: int = 6) -> dict:
    rounds: list[dict] = []
    asked = {a["question"] for a in profile.get("user_answers", [])}
    feedback, previous = "", ""

    for n in range(1, max_rounds + 1):
        resume = write(profile, jd, feedback, previous)
        ats_result = ats(resume, jd)
        rev = review(profile, jd, resume, ats_result)
        rnd = {"round": n, "resume": resume, "ats": ats_result, "review": rev}
        rounds.append(rnd)
        on_round(rnd)
        logger.info("round %d: ATS %s, review %s/10", n, ats_result["score"], rev["score"])
        if _passes(rnd):
            break

        new_qs = [q for q in rev["missing_from_profile"] if q not in asked]
        if new_qs:
            asked.update(new_qs)
            for q, a in (ask_gaps(new_qs) or {}).items():
                if a and a.strip():
                    profile.setdefault("user_answers", []).append(
                        {"question": q, "answer": a.strip(), "source": "user"})

        feedback = "\n".join(
            [f"ATS: {i}" for i in ats_result.get("issues", [])]
            + [f"Reviewer: {i}" for i in rev["issues"]]
            + [f"remove: {f}" for f in rev["fabrications"]])
        previous = resume

    best = max(rounds, key=_rank)
    return {"resume": best["resume"], "ats": best["ats"], "review": best["review"],
            "rounds": rounds, "reached_target": _passes(best)}
