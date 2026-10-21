import re
from fpdf import FPDF

from src.sanitizer import has_dashes

_SECTION_HEADINGS = {
    "summary", "education", "work experience", "projects",
    "technical skills", "achievements & certifications",
    "achievements and certifications", "skills", "experience",
    "certifications", "links",
}

_EDU_KEYWORDS = {"university", "college", "institute", "school", "b.tech",
                 "b.s.", "b.sc.", "m.tech", "m.s.", "ph.d", "degree",
                 "bachelor", "master", "cgpa", "gpa"}


class _CVPDF(FPDF):
    def __init__(self):
        super().__init__(format="A4")
        self.set_auto_page_break(auto=False)
        self._font_name = "Times"
        self._base_size = 10.5
        self._line_h = 4.6
        self._small_gap = 1.5
        self._section_gap = 2.0
        self.set_margins(15, 10, 15)

    def _set_sizes(self, base: float):
        self._base_size = base
        self._line_h = base * 0.46
        self._small_gap = base * 0.16
        self._section_gap = base * 0.22

    def _draw_titlerule(self):
        y = self.get_y() + 1
        self.set_draw_color(0, 0, 0)
        self.set_line_width(0.4)
        self.line(self.l_margin, y, self.w - self.r_margin, y)
        self.ln(3)

    def _is_section_heading(self, line: str) -> bool:
        normalized = line.strip().lower().rstrip(":")
        return normalized in _SECTION_HEADINGS

    def _is_education_line(self, line: str) -> bool:
        low = line.lower()
        return any(k in low for k in _EDU_KEYWORDS)

    def _has_date_range(self, line: str) -> bool:
        return bool(re.search(
            r"(?:20\d{2}|19\d{2})\s*[-–—to]+\s*(?:20\d{2}|19\d{2}|present|current|now)",
            line, re.I))

    def _has_right_date(self, line: str) -> bool:
        return bool(re.search(
            r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{4}\s*"
            r"[-–—to]+\s*(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+)?"
            r"\d{4}\b",
            line, re.I)) or self._has_date_range(line)

    def _split_title_date(self, line: str) -> tuple[str, str]:
        patterns = [
            r"^(.*?)\s{2,}(\d{4}\s*[-–—to]+\s*(?:20\d{2}|present|current|now).*)$",
            r"^(.*?)\s{2,}(.*(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{4}.*)$",
            r"^(.*?)\s{2,}((?:20\d{2}|19\d{2})\s*[-–—to]+.*)$",
        ]
        for pat in patterns:
            m = re.match(pat, line, re.I)
            if m:
                return m.group(1).strip(), m.group(2).strip()
        return line, ""

    def _is_bullet(self, line: str) -> bool:
        stripped = line.strip()
        return stripped.startswith("•") or stripped.startswith("-") or stripped.startswith("*")

    def _clean_bullet(self, line: str) -> str:
        return re.sub(r"^[\s]*[•\-*]\s*", "", line.strip())

    def _is_skill_category(self, line: str) -> bool:
        return bool(re.match(
            r"^\s{0,5}(?:Core|Language|System|Cloud|Database|Framework|AI|Tool|Method|DevOps|Libraries|Platforms)\w*\s*[:\-]",
            line, re.I))

    def render(self, cv_text: str, out_path: str) -> str:
        lines = cv_text.split("\n")
        for base in [10.5, 10.0, 9.5, 9.0, 8.5, 8.0, 7.5, 7.0, 6.5, 6.0]:
            self._set_sizes(base)
            self.add_page()
            self._render_lines(lines)
            if self.get_y() <= 275:
                break
            self.delete_page(self.page())

        self.output(out_path)
        return out_path

    def _render_lines(self, lines: list[str]):
        x0 = self.l_margin
        w = self.w - self.l_margin - self.r_margin
        first_heading = True

        for raw in lines:
            line = raw.rstrip()
            stripped = line.strip()

            if not stripped:
                self.ln(self._small_gap)
                continue

            if self.get_y() > 275:
                return

            y = self.get_y()

            # Name line: centered, large bold, small caps feel
            if (y < 18
                    and not self._is_section_heading(stripped)
                    and not self._is_bullet(stripped)
                    and not self._is_skill_category(stripped)
                    and len(stripped) > 3
                    and not any(c.isdigit() for c in stripped[:4])
                    and len(stripped.split()) <= 5):
                self.set_font(self._font_name, "B", self._base_size + 5)
                self.cell(w, self._line_h + 3, stripped.upper(), align="C",
                          new_x="LMARGIN", new_y="NEXT")
                self.ln(0.5)
                continue

            # Contact line: centered, small, pipe separators
            if (y < 28
                    and ("@" in stripped
                         or "linkedin" in stripped.lower()
                         or "github" in stripped.lower()
                         or "portfolio" in stripped.lower()
                         or re.match(r"^\+?\d[\d\s\-()]{8,}", stripped))):
                self.set_font(self._font_name, "", self._base_size - 2)
                self.cell(w, self._line_h, stripped, align="C",
                          new_x="LMARGIN", new_y="NEXT")
                self.ln(1)
                continue

            # Section heading: small caps, left-aligned, with titlerule
            if self._is_section_heading(stripped):
                if not first_heading:
                    self.ln(self._section_gap)
                first_heading = False
                self.set_font(self._font_name, "B", self._base_size + 0.5)
                heading_text = stripped.upper()
                self.cell(w, self._line_h + 1, heading_text,
                          new_x="LMARGIN", new_y="NEXT")
                self._draw_titlerule()
                continue

            # Title + date on same line (tabular: bold left, right-aligned date)
            title, date = self._split_title_date(stripped)
            if date:
                self.set_font(self._font_name, "B", self._base_size)
                self.cell(w * 0.72, self._line_h, title, new_x="END")
                self.set_font(self._font_name, "", self._base_size - 0.5)
                self.cell(w * 0.28, self._line_h, date, align="R",
                          new_x="LMARGIN", new_y="NEXT")
                continue

            # Education line: institution left, details right
            if self._is_education_line(stripped) and not self._has_right_date(stripped):
                parts = re.split(r"\s{2,}", stripped, maxsplit=1)
                if len(parts) == 2:
                    self.set_font(self._font_name, "", self._base_size)
                    self.cell(w * 0.6, self._line_h, parts[0], new_x="END")
                    self.set_font(self._font_name, "", self._base_size - 0.5)
                    self.cell(w * 0.4, self._line_h, parts[1], align="R",
                              new_x="LMARGIN", new_y="NEXT")
                    continue

            # Bullet point: small, indented with small bullet
            if self._is_bullet(stripped):
                self.set_font(self._font_name, "", self._base_size - 0.5)
                indent = x0 + 5
                self.set_x(indent)
                text = self._clean_bullet(stripped)
                self.cell(3, self._line_h, "o", new_x="END")
                self.multi_cell(w - 8, self._line_h, text)
                self.ln(0.5)
                continue

            # Technical Skills: bold category label + skills
            if self._is_skill_category(stripped):
                self.set_font(self._font_name, "", self._base_size - 0.5)
                self.set_x(x0 + 5)
                m = re.match(
                    r"^(\s*(?:Core|Language|System|Cloud|Database|Framework|AI|Tool|Method|DevOps|Libraries|Platforms)\w*\s*[:\-])\s*(.*)",
                    stripped, re.I)
                if m:
                    cat = m.group(1).strip().rstrip(":").rstrip("-")
                    skills = m.group(2)
                    self.set_font(self._font_name, "B", self._base_size - 0.5)
                    cat_w = self.get_string_width(cat + ": ") + 1
                    self.cell(cat_w, self._line_h, cat + ":", new_x="END")
                    self.set_font(self._font_name, "", self._base_size - 0.5)
                    self.multi_cell(w - cat_w - 5, self._line_h, skills)
                    self.ln(0.3)
                    continue

            # Default: paragraph text
            self.set_font(self._font_name, "", self._base_size - 0.5)
            self.set_x(x0)
            self.multi_cell(w, self._line_h, stripped)
            self.ln(0.3)


# The core Times font is latin-1 only; map common typographic characters to
# ASCII and drop anything else (emoji, non-Latin scripts) so export never crashes.
_ASCII_MAP = str.maketrans({"\u201c": '"', "\u201d": '"', "\u2018": "'",
                            "\u2019": "'", "\u2026": "..."})


def export_pdf(cv_text: str, out_path: str) -> str:
    cv_text = cv_text.translate(_ASCII_MAP)
    cv_text = "".join(c if c == "\u2022" or ord(c) < 256 else "" for c in cv_text)
    if has_dashes(cv_text):
        raise ValueError("cv_text still contains dashes; sanitize before export")

    pdf = _CVPDF()
    pdf.render(cv_text, out_path)
    return out_path
