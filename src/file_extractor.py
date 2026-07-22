from __future__ import annotations

import os


class ExtractError(Exception):
    pass


def extract_text(file_path: str) -> str:
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".pdf":
        return _extract_pdf(file_path)
    elif ext in (".docx", ".doc"):
        return _extract_docx(file_path)
    elif ext in (".txt", ".md", ".rtf"):
        return _extract_plain(file_path)
    else:
        raise ExtractError(f"Unsupported file type: {ext}. Use PDF, DOCX, or TXT.")


def _extract_pdf(path: str) -> str:
    try:
        from PyPDF2 import PdfReader
    except ImportError:
        raise ExtractError("PyPDF2 not installed. Run: pip install PyPDF2")
    try:
        reader = PdfReader(path)
        pages = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                pages.append(text)
        text = "\n".join(pages).strip()
        if not text:
            raise ExtractError("No readable text found in PDF")
        return text
    except ExtractError:
        raise
    except Exception as exc:
        raise ExtractError(f"Failed to read PDF: {exc}") from exc


def _extract_docx(path: str) -> str:
    try:
        import docx
    except ImportError:
        raise ExtractError("python-docx not installed. Run: pip install python-docx")
    try:
        doc = docx.Document(path)
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        text = "\n".join(paragraphs).strip()
        if not text:
            raise ExtractError("No readable text found in DOCX")
        return text
    except ExtractError:
        raise
    except Exception as exc:
        raise ExtractError(f"Failed to read DOCX: {exc}") from exc


def _extract_plain(path: str) -> str:
    try:
        for encoding in ("utf-8", "latin-1", "cp1252"):
            try:
                with open(path, encoding=encoding) as f:
                    text = f.read().strip()
                if text:
                    return text
            except UnicodeDecodeError:
                continue
        raise ExtractError("Could not decode file")
    except ExtractError:
        raise
    except Exception as exc:
        raise ExtractError(f"Failed to read file: {exc}") from exc
