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
