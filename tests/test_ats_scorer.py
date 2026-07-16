from src.ats_scorer import extract_keywords, score_cv


def test_extract_keywords_drops_stopwords_and_ranks_by_frequency():
    jd = "Python python python developer developer needs SQL and the the the"
    kws = extract_keywords(jd, top_n=5)
    assert "python" in kws
    assert "developer" in kws
    assert "the" not in kws
    assert kws[0] == "python"


def test_score_high_for_well_matched_cv():
    jd = "Seeking Python developer with SQL, AWS, Docker and testing experience."
    cv = (
        "Summary: Python developer.\n"
        "Experience: Built SQL pipelines on AWS using Docker.\n"
        "Skills: Python, SQL, AWS, Docker, testing.\n"
        "Education: BS Computer Science.\n"
        "Contact: jane@example.com. Increased throughput by 40%. Led testing."
    )
    result = score_cv(cv, jd)
    assert result["score"] >= 85
    assert result["missing_keywords"] == []


def test_score_reports_missing_keywords():
    jd = "Need Python, Kubernetes, and Terraform skills."
    cv = "Summary. Experience with Python. Skills: Python. Education. a@b.com"
    result = score_cv(cv, jd)
    assert "kubernetes" in result["missing_keywords"]
    assert "terraform" in result["missing_keywords"]


def test_dashes_penalize_score():
    jd = "Python developer with SQL and AWS."
    clean = "Summary. Python SQL AWS. Skills Python SQL AWS. Experience. Education. a@b.com 40%"
    dirty = clean + " fast-paced"
    assert score_cv(dirty, jd)["score"] < score_cv(clean, jd)["score"]
