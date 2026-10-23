from PyPDF2 import PdfReader

from src import resume_pdf

RESUME = {
    "name": "Asha Rao",
    "contact": {"phone": "+91 98765 43210", "email": "asha@x.com",
                "linkedin": "linkedin.com/in/asha-rao", "github": "https://github.com/asha-rao"},
    "education": [{"school": "IIT Madras", "location": "Chennai", "degree": "B.Tech CSE",
                   "dates": "2020 to 2024"}],
    "experience": [{"title": "SDE Intern", "company": "Acme <Labs>", "location": "Remote",
                    "dates": "May 2023 to Jul 2023",
                    "bullets": [f"Built service {i} serving 1,000 requests per second" for i in range(12)]}],
    "projects": [{"name": "Kite", "tech": ["Python", "Redis"], "link": "kite-app.dev",
                  "bullets": [f"Scheduled {i},000 jobs with retries" for i in range(12)]}],
    "skills": [{"category": "Languages", "items": ["Python", "Go"]}],
}


def test_html_escapes_text_and_links_contacts():
    html = resume_pdf.to_html(RESUME)
    assert "Acme &lt;Labs&gt;" in html
    assert 'href="mailto:asha@x.com"' in html
    assert 'href="https://linkedin.com/in/asha-rao"' in html
    assert '>github.com/asha-rao</a>' in html
    assert 'href="https://kite-app.dev"' in html


def test_render_pdf_one_page_with_links_and_text(tmp_path, monkeypatch):
    monkeypatch.setattr(resume_pdf, "_FONT", "data:text/css,")  # no network in tests
    out = tmp_path / "r.pdf"
    resume_pdf.render_pdf(RESUME, str(out))
    reader = PdfReader(str(out))
    assert len(reader.pages) == 1
    text = reader.pages[0].extract_text()
    assert "Asha Rao" in text and "SDE Intern" in text and "TECHNICAL SKILLS" in text
    assert "EDUCATION" in text
    uris = {a.get_object()["/A"]["/URI"].rstrip("/") for a in reader.pages[0].get("/Annots", [])}
    assert {"mailto:asha@x.com", "https://github.com/asha-rao", "https://kite-app.dev"} <= uris
