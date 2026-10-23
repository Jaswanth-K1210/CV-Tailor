"""Render a structured resume (see tailor.write_resume) as Jake's resume template PDF.

HTML + CSS printed by Playwright's Chromium: real clickable links, selectable text for
ATS parsing, and no LaTeX install on the user's machine.
"""
from __future__ import annotations

from html import escape

# Jake's template is set in Computer Modern; fall back to Times if the font can't load.
_FONT = "https://cdn.jsdelivr.net/gh/aaaakshat/cm-web-fonts@latest/font/Serif/cmun-serif.css"

_CSS = """
@page { size: A4; margin: 0.45in 0.5in; }
* { box-sizing: border-box; }
html { font-size: calc(10.5pt * var(--s, 1)); }
body { margin: 0; font-family: "Computer Modern Serif", "Times New Roman", serif; color: #000; line-height: 1.18; }
a { color: inherit; text-decoration: underline; }
header { text-align: center; margin-bottom: 0.35rem; }
h1 { font-size: 2.2rem; font-weight: 700; margin: 0 0 0.15rem; }
.contact { font-size: 0.92rem; }
.contact span + span::before { content: " | "; text-decoration: none; }
/* Uppercase rather than font-variant: small-caps, which Chromium fakes with split
   glyph runs that ATS parsers read as "EDUCA TION". */
h2 { font-size: 1.02rem; text-transform: uppercase; letter-spacing: 0.04em; font-weight: 400; margin: 0.55rem 0 0.25rem;
     border-bottom: 0.6pt solid #000; padding-bottom: 0.05rem; }
.entry { margin: 0 0 0.25rem 0.6rem; }
.row { display: flex; justify-content: space-between; gap: 1rem; }
.row .r { white-space: nowrap; }
.sub { font-size: 0.9rem; font-style: italic; }
ul { margin: 0.1rem 0 0.15rem 1.7rem; padding: 0; }
li { font-size: 0.9rem; margin: 0 0 0.08rem; padding-left: 0.15rem; }
.skills { margin-left: 0.6rem; font-size: 0.92rem; }
.skills div { margin-bottom: 0.08rem; }
"""


def _url(value: str) -> str:
    v = value.strip()
    if "@" in v and not v.startswith(("http", "mailto:")):
        return "mailto:" + v
    if v.startswith(("http://", "https://", "mailto:", "tel:")):
        return v
    return "https://" + v


def _link(value: str, text: str | None = None) -> str:
    return f'<a href="{escape(_url(value))}">{escape(text or value)}</a>'


def _display(value: str) -> str:
    return value.removeprefix("https://").removeprefix("http://").removeprefix("www.").rstrip("/")


def _bullets(items) -> str:
    items = [b for b in (items or []) if b]
    return f"<ul>{''.join(f'<li>{escape(b)}</li>' for b in items)}</ul>" if items else ""


def _two_rows(left1, right1, left2, right2) -> str:
    html = f'<div class="row"><b>{escape(left1)}</b><span class="r">{escape(right1)}</span></div>'
    if left2 or right2:
        html += f'<div class="row sub"><span>{escape(left2)}</span><span class="r">{escape(right2)}</span></div>'
    return html


def to_html(r: dict) -> str:
    c = r.get("contact") or {}
    parts = []
    if c.get("phone"):
        parts.append(f"<span>{escape(c['phone'])}</span>")
    if c.get("email"):
        parts.append(f"<span>{_link(c['email'])}</span>")
    for key in ("linkedin", "github", "website"):
        if c.get(key):
            parts.append(f"<span>{_link(c[key], _display(c[key]))}</span>")
    if c.get("location"):
        parts.append(f"<span>{escape(c['location'])}</span>")

    body = [f'<header><h1>{escape(r.get("name", ""))}</h1><div class="contact">{"".join(parts)}</div></header>']

    if r.get("education"):
        body.append("<h2>Education</h2>")
        for e in r["education"]:
            body.append(f'<div class="entry">{_two_rows(e.get("school", ""), e.get("location", ""), e.get("degree", ""), e.get("dates", ""))}{_bullets(e.get("details"))}</div>')
    if r.get("experience"):
        body.append("<h2>Experience</h2>")
        for e in r["experience"]:
            body.append(f'<div class="entry">{_two_rows(e.get("title", ""), e.get("dates", ""), e.get("company", ""), e.get("location", ""))}{_bullets(e.get("bullets"))}</div>')
    if r.get("projects"):
        body.append("<h2>Projects</h2>")
        for p in r["projects"]:
            name = f"<b>{escape(p.get('name', ''))}</b>"
            if p.get("link"):
                name = f"<b>{_link(p['link'], p.get('name', ''))}</b>"
            tech = f" | <i>{escape(', '.join(p.get('tech') or []))}</i>" if p.get("tech") else ""
            body.append(f'<div class="entry"><div class="row"><span>{name}{tech}</span>'
                        f'<span class="r">{escape(p.get("dates", ""))}</span></div>{_bullets(p.get("bullets"))}</div>')
    if r.get("skills"):
        body.append('<h2>Technical Skills</h2><div class="skills">')
        body.extend(f"<div><b>{escape(s.get('category', ''))}</b>: {escape(', '.join(s.get('items') or []))}</div>"
                    for s in r["skills"])
        body.append("</div>")

    return (f'<!doctype html><html><head><meta charset="utf-8"><link rel="stylesheet" href="{_FONT}">'
            f"<style>{_CSS}</style></head><body>{''.join(body)}</body></html>")


# A4 printable area with the @page margins above, in CSS px (96 per inch).
_PRINT_W = round((8.27 - 1.0) * 96)
_PRINT_H = round((11.69 - 0.9) * 96)


def render_pdf(resume: dict, out_path: str) -> str:
    from playwright.sync_api import sync_playwright

    html = to_html(resume)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": _PRINT_W, "height": _PRINT_H})
            page.emulate_media(media="print")
            try:
                page.set_content(html, wait_until="networkidle", timeout=15000)
            except Exception:
                page.set_content(html.replace(_FONT, ""))  # offline: Times fallback
            # Shrink the type a step at a time until everything fits on one page.
            for scale in (1, 0.96, 0.92, 0.88, 0.85, 0.82, 0.79, 0.76):
                page.evaluate(f"document.documentElement.style.setProperty('--s', '{scale}')")
                if page.evaluate("document.body.scrollHeight") <= _PRINT_H:
                    break
            page.pdf(path=out_path, prefer_css_page_size=True, print_background=True)
        finally:
            browser.close()
    return out_path
