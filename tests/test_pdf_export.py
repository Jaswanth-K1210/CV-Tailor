import os

import pytest

from src.pdf_export import export_pdf


def test_export_pdf_creates_file(tmp_path):
    out = str(tmp_path / "cv.pdf")
    cv = "Summary\nExperienced developer.\nSkills\nPython, SQL"
    result = export_pdf(cv, out)
    assert result == out
    assert os.path.exists(out)
    assert os.path.getsize(out) > 0
    with open(out, "rb") as f:
        assert f.read(4) == b"%PDF"


def test_export_pdf_rejects_dashes(tmp_path):
    out = str(tmp_path / "cv.pdf")
    with pytest.raises(ValueError):
        export_pdf("fast-paced role", out)


def test_export_pdf_handles_unicode(tmp_path):
    from src.pdf_export import export_pdf
    out = tmp_path / "u.pdf"
    export_pdf("ASHA RAO\nasha@x.com | “quoted” ‘x’ café … 🚀\n\nEDUCATION\nIIT  2020 to 2024\n", str(out))
    assert out.stat().st_size > 0


def test_export_pdf_long_cv_shrinks_to_one_page(tmp_path):
    from PyPDF2 import PdfReader
    from src.pdf_export import export_pdf
    body = "\n".join(f"  • Built service number {i} handling 1,000 requests per second" for i in range(70))
    out = tmp_path / "long.pdf"
    export_pdf("ASHA RAO\nasha@x.com\n\nEXPERIENCE\n" + body, str(out))
    assert len(PdfReader(str(out)).pages) == 1


def test_export_pdf_inline_bullet_char(tmp_path):
    from src.pdf_export import export_pdf
    out = tmp_path / "b.pdf"
    export_pdf("ASHA RAO\n\nSKILLS\n  Languages: Python • Go • SQL\n  • Built X\n", str(out))
    assert out.stat().st_size > 0


def test_bullet_text_is_not_glued_to_marker(tmp_path):
    from PyPDF2 import PdfReader
    from src.pdf_export import export_pdf
    out = tmp_path / "g.pdf"
    export_pdf("ASHA RAO\n\nEXPERIENCE\n  • Built a scheduler\n", str(out))
    text = PdfReader(str(out)).pages[0].extract_text()
    assert "Built a scheduler" in text and "oBuilt" not in text
