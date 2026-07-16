import os
import subprocess
import time

import webview

from src import ats_scorer, generator, jd_fetcher, sanitizer
from src.orchestrator import generate_until_target
from src.pdf_export import export_pdf


class Api:
    def check_engine(self) -> dict:
        try:
            r = subprocess.run(["claude", "--version"], capture_output=True,
                               text=True, timeout=15)
            ok = r.returncode == 0
            return {"ok": ok, "version": r.stdout.strip()}
        except Exception as exc:  # noqa: BLE001 - report any failure to the UI
            return {"ok": False, "error": str(exc)}

    def fetch_jd(self, url: str) -> dict:
        try:
            return {"ok": True, "jd": jd_fetcher.fetch_jd(url)}
        except jd_fetcher.FetchError as exc:
            return {"ok": False, "error": str(exc)}

    def generate(self, cv: str, jd: str, feedback: str, previous: str) -> dict:
        if not cv.strip() or not jd.strip():
            return {"ok": False, "error": "Both CV and job description are required."}
        keywords = set(ats_scorer.extract_keywords(jd))

        def sanitize_fn(text: str) -> str:
            return sanitizer.remove_dashes(text)

        try:
            result = generate_until_target(
                cv, jd, feedback, previous,
                generate_fn=generator.generate_cv,
                score_fn=ats_scorer.score_cv,
                sanitize_fn=sanitize_fn,
            )
        except generator.EngineError as exc:
            return {"ok": False, "error": str(exc)}

        result["repeated_words"] = sanitizer.find_repeated_words(
            result["cv"], protected=keywords)
        result["ok"] = True
        return result

    def export_pdf(self, cv: str) -> dict:
        clean = sanitizer.remove_dashes(cv)
        out = os.path.join(os.path.expanduser("~"), "Desktop",
                           f"tailored_cv_{int(time.time())}.pdf")
        try:
            export_pdf(clean, out)
            return {"ok": True, "path": out}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc)}


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    index = os.path.join(here, "..", "web", "index.html")
    webview.create_window("CV Tailor", index, js_api=Api(),
                          width=980, height=820, min_size=(760, 620))
    webview.start()
