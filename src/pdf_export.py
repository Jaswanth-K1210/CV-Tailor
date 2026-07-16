from fpdf import FPDF

from src.sanitizer import has_dashes


def export_pdf(cv_text: str, out_path: str) -> str:
    if has_dashes(cv_text):
        raise ValueError("cv_text still contains dashes; sanitize before export")

    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", size=11)

    for raw_line in cv_text.split("\n"):
        line = raw_line.rstrip()
        if not line:
            pdf.ln(4)
            continue
        pdf.set_x(pdf.l_margin)
        is_heading = len(line) < 40 and not line.endswith(".")
        if is_heading:
            pdf.set_font("Helvetica", style="B", size=13)
            pdf.multi_cell(w=0, h=7, text=line)
            pdf.set_font("Helvetica", size=11)
        else:
            pdf.multi_cell(w=0, h=6, text=line)

    pdf.output(out_path)
    return out_path
