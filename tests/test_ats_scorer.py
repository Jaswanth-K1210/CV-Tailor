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
        "Jane Smith\n"
        "555-123-4567 | jane@example.com | linkedin.com/in/janesmith | github.com/janesmith\n"
        "\n"
        "Summary\n"
        "Software developer with 4 years of experience building scalable backend systems using Python, SQL, and AWS.\n"
        "\n"
        "Education\n"
        "Stanford University 2019 to 2023\n"
        "B.S. in Computer Science GPA: 3.8\n"
        "\n"
        "Experience\n"
        "Google (Software Developer) Jan 2023 to Present\n"
        "   \u2022 Built data pipelines using Python, SQL, and AWS processing 10M records daily.\n"
        "   \u2022 Implemented Docker-based testing framework reducing deploy time by 40 percent.\n"
        "   \u2022 Led migration of legacy services to AWS Lambda saving 50K dollars annually.\n"
        "   \u2022 Conducted code reviews and mentored 2 junior developers on best practices.\n"
        "\n"
        "Projects\n"
        "DataFlow Engine | Python, SQL, AWS, Docker\n"
        "   \u2022 Designed distributed data pipeline processing 500K events per second.\n"
        "   \u2022 Automated testing suite with 95 percent coverage using pytest and Docker.\n"
        "   \u2022 Built REST API serving 500 concurrent users with sub-second response times.\n"
        "\n"
        "Technical Skills\n"
        "  Languages: Python, SQL, JavaScript, Go\n"
        "  Cloud & DevOps: AWS, Docker, Kubernetes, GitHub Actions\n"
        "  Frameworks: FastAPI, Flask, React\n"
        "\n"
        "Certifications\n"
        "   \u2022 AWS Certified Solutions Architect Associate 2024\n"
        "   \u2022 Google Cloud Professional Developer 2023\n"
    )
    result = score_cv(cv, jd)
    assert result["score"] >= 80
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
    assert score_cv(dirty, jd)["score"] <= score_cv(clean, jd)["score"]
