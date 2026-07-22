import logging

logger = logging.getLogger(__name__)


def generate_until_target(source_cv, jd, feedback, previous_draft,
                          generate_fn, score_fn, sanitize_fn,
                          target: int = 75, max_retries: int = 1) -> dict:
    attempts = 0
    missing: list[str] = []
    prev = previous_draft
    result = {"cv": "", "score": 0, "missing_keywords": [], "notes": [],
              "attempts": 0}

    while attempts <= max_retries:
        logger.info("attempt %d/%d (target score %d)", attempts + 1, max_retries + 1, target)
        try:
            cv = sanitize_fn(generate_fn(source_cv, jd, feedback, prev, missing))
        except Exception:
            logger.exception("generate_fn raised on attempt %d", attempts + 1)
            raise
        attempts += 1
        scored = score_fn(cv, jd)
        result = {
            "cv": cv,
            "score": scored["score"],
            "missing_keywords": scored["missing_keywords"],
            "notes": scored["notes"],
            "attempts": attempts,
        }
        logger.info("score: %d  (missing_kw: %s)", scored["score"],
                     ", ".join(scored["missing_keywords"][:10]) or "none")
        if scored["score"] >= target:
            logger.info("target reached in %d attempt(s)", attempts)
            break
        missing = scored["missing_keywords"]
        prev = cv
        feedback = ""

    return result
