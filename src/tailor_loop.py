from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

ATS_TARGET = 85      # must be strictly above
REVIEW_TARGET = 9    # must be at least
PATIENCE = 2         # stop after this many rounds without beating the best so far


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
    gaps_asked = False
    feedback, previous = "", ""
    error = None
    best_rank, stale = None, 0

    for n in range(1, max_rounds + 1):
        try:
            resume = write(profile, jd, feedback, previous)
            ats_result = ats(resume, jd)
            rev = review(profile, jd, resume, ats_result)
        except Exception as exc:
            if not rounds:
                raise
            # Don't throw away finished rounds because a later one failed.
            logger.exception("round %d failed; delivering best so far", n)
            error = f"round {n} failed: {exc}"
            break
        rnd = {"round": n, "resume": resume, "ats": ats_result, "review": rev}
        rounds.append(rnd)
        on_round(rnd)
        logger.info("round %d: ATS %s, review %s/10", n, ats_result["score"], rev["score"])
        if _passes(rnd):
            break
        # More rounds can't add experience the profile lacks; stop when stuck
        # instead of spending the user's AI quota on all 6.
        if best_rank is None or _rank(rnd) > best_rank:
            best_rank, stale = _rank(rnd), 0
        else:
            stale += 1
            if stale >= PATIENCE:
                logger.info("no improvement for %d rounds; stopping", PATIENCE)
                break

        # ponytail: one round of gap questions per run; the reviewer rewords the
        # same question every round, so text dedupe alone isn't enough.
        new_qs = [q for q in rev["missing_from_profile"] if q not in asked]
        if new_qs and not gaps_asked:
            gaps_asked = True
            asked.update(new_qs)
            answers = ask_gaps(new_qs) or {}
            for q in new_qs:
                # Skipped questions are kept too so the reviewer doesn't re-ask them reworded.
                a = (answers.get(q) or "").strip() or "(skipped, no experience to add)"
                profile.setdefault("user_answers", []).append(
                    {"question": q, "answer": a, "source": "user"})

        # Always revise the best draft so far with its own feedback; revising a
        # worse draft just loses what the better one got right.
        base = max(rounds, key=_rank)
        feedback = "\n".join(
            [f"ATS: {i}" for i in base["ats"].get("issues", [])]
            + [f"Reviewer: {i}" for i in base["review"]["issues"]]
            + [f"remove: {f}" for f in base["review"]["fabrications"]])
        previous = base["resume"]

    best = max(rounds, key=_rank)
    return {"resume": best["resume"], "ats": best["ats"], "review": best["review"],
            "rounds": rounds, "reached_target": _passes(best), "error": error}
