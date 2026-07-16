from src.orchestrator import generate_until_target


def _score_fn_factory(scores):
    calls = {"i": 0}

    def score_fn(cv, jd):
        i = calls["i"]
        calls["i"] += 1
        s = scores[min(i, len(scores) - 1)]
        return {"score": s, "missing_keywords": ["aws"] if s < 85 else [],
                "notes": []}
    return score_fn


def test_stops_early_when_target_met():
    seen = {"count": 0}

    def generate_fn(*a, **k):
        seen["count"] += 1
        return "CV"

    result = generate_until_target(
        "cv", "jd", "", "",
        generate_fn=generate_fn,
        score_fn=_score_fn_factory([90]),
        sanitize_fn=lambda c: c,
    )
    assert result["score"] == 90
    assert result["attempts"] == 1
    assert seen["count"] == 1


def test_retries_until_target_then_stops():
    seen = {"count": 0}

    def generate_fn(*a, **k):
        seen["count"] += 1
        return "CV"

    result = generate_until_target(
        "cv", "jd", "", "",
        generate_fn=generate_fn,
        score_fn=_score_fn_factory([70, 80, 88]),
        sanitize_fn=lambda c: c,
    )
    assert result["score"] == 88
    assert result["attempts"] == 3


def test_caps_at_max_retries():
    result = generate_until_target(
        "cv", "jd", "", "",
        generate_fn=lambda *a, **k: "CV",
        score_fn=_score_fn_factory([50, 50, 50, 50, 50]),
        sanitize_fn=lambda c: c,
        max_retries=3,
    )
    assert result["attempts"] == 4  # first try + 3 retries
    assert result["score"] == 50


def test_sanitize_is_applied_to_output():
    result = generate_until_target(
        "cv", "jd", "", "",
        generate_fn=lambda *a, **k: "fast-paced",
        score_fn=_score_fn_factory([90]),
        sanitize_fn=lambda c: c.replace("-", " "),
    )
    assert result["cv"] == "fast paced"
