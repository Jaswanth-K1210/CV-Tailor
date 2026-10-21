from src.tailor_loop import run


def _run(ats_scores, reviews, ask_gaps=lambda qs: {}, profile=None):
    calls = {"write": [], "i": 0}

    def write(profile, jd, feedback, previous):
        calls["write"].append(feedback)
        return f"cv{len(calls['write'])}"

    def ats(text, jd):
        return {"score": ats_scores[min(calls["i"], len(ats_scores) - 1)], "issues": ["ats issue"]}

    def review(profile, jd, resume, ats_result):
        r = reviews[min(calls["i"], len(reviews) - 1)]
        calls["i"] += 1
        return {"score": 0, "issues": [], "fabrications": [], "missing_from_profile": [], **r}

    profile = profile if profile is not None else {}
    result = run(profile, "jd", write=write, review=review, ats=ats, ask_gaps=ask_gaps)
    return result, calls, profile


def test_stops_when_both_targets_met():
    result, calls, _ = _run([70, 90], [{"score": 9}])
    assert result["reached_target"] is True
    assert len(result["rounds"]) == 2
    assert result["resume"] == "cv2"
    assert "ats issue" in calls["write"][1]


def test_ats_85_exactly_does_not_pass():
    result, _, _ = _run([85], [{"score": 10}])
    assert result["reached_target"] is False
    assert len(result["rounds"]) == 6


def test_fabrications_block_done():
    result, calls, _ = _run([95], [{"score": 9, "fabrications": ["fake AWS cert"]}, {"score": 9}])
    assert len(result["rounds"]) == 2
    assert "remove: fake AWS cert" in calls["write"][1]


def test_caps_at_six_and_returns_best():
    scores = [{"score": s} for s in (5, 8, 6, 7, 6, 5)]
    result, _, _ = _run([90], scores)
    assert len(result["rounds"]) == 6
    assert result["reached_target"] is False
    assert result["resume"] == "cv2"


def test_gap_asked_once_and_saved_to_profile():
    asked = []

    def ask_gaps(qs):
        asked.extend(qs)
        return {q: "Used it at Acme" for q in qs}

    gap = {"score": 7, "missing_from_profile": ["Have you used Kubernetes?"]}
    result, _, profile = _run([90], [gap, gap, {"score": 9}], ask_gaps=ask_gaps)
    assert asked == ["Have you used Kubernetes?"]
    assert profile["user_answers"] == [
        {"question": "Have you used Kubernetes?", "answer": "Used it at Acme", "source": "user"}]
    assert result["reached_target"] is True


def test_skipped_gap_is_remembered():
    gap = {"score": 7, "missing_from_profile": ["Django?"]}
    _, _, profile = _run([90], [gap, {"score": 9}], ask_gaps=lambda qs: {})
    assert profile["user_answers"][0]["question"] == "Django?"
    assert "skipped" in profile["user_answers"][0]["answer"]


def test_gaps_asked_only_in_one_round():
    asked = []
    reviews = [{"score": 7, "missing_from_profile": ["Django?"]},
               {"score": 7, "missing_from_profile": ["Used Django at all?"]}]
    _run([90], reviews, ask_gaps=lambda qs: asked.extend(qs) or {})
    assert asked == ["Django?"]
