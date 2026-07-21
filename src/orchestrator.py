def generate_until_target(source_cv, jd, feedback, previous_draft,
                          generate_fn, score_fn, sanitize_fn,
                          target: int = 85, max_retries: int = 1) -> dict:
    attempts = 0
    missing: list[str] = []
    prev = previous_draft
    result = {"cv": "", "score": 0, "missing_keywords": [], "notes": [],
              "attempts": 0}

    while attempts <= max_retries:
        cv = sanitize_fn(generate_fn(source_cv, jd, feedback, prev, missing))
        attempts += 1
        scored = score_fn(cv, jd)
        result = {
            "cv": cv,
            "score": scored["score"],
            "missing_keywords": scored["missing_keywords"],
            "notes": scored["notes"],
            "attempts": attempts,
        }
        if scored["score"] >= target:
            break
        missing = scored["missing_keywords"]
        prev = ""
        feedback = ""

    return result
