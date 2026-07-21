import os
import platform
import time

import webview

from src import ats_scorer, generator, jd_fetcher, sanitizer
from src.engines import get_engine, available_engines, ENGINE_LABELS, DEFAULT_MODELS
from src.orchestrator import generate_until_target
from src.pdf_export import export_pdf
import src.settings as settings

_external_scorer_available = False
try:
    from ats_resume_checker import analyzer as _ext_analyzer
    _external_scorer_available = True
except ImportError:
    pass


class Api:
    def check_engine(self) -> dict:
        cfg = settings.load()
        engine_name = cfg.get("engine", "claude")
        try:
            engine = get_engine(engine_name)
            return engine.check()
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def get_engines(self) -> dict:
        return {"ok": True, "engines": available_engines()}

    def get_settings(self) -> dict:
        cfg = settings.load()
        engine_name = cfg.get("engine", "claude")
        return {
            "ok": True,
            "engine": engine_name,
            "model": cfg.get("model", DEFAULT_MODELS.get(engine_name, "")),
            "budget_usd": cfg.get("budget_usd", 0.10),
            "engine_label": ENGINE_LABELS.get(engine_name, engine_name),
            "default_model": DEFAULT_MODELS.get(engine_name, ""),
        }

    def save_settings(self, engine: str, model: str, budget_usd: float) -> dict:
        try:
            settings.save({
                "engine": engine,
                "model": model,
                "budget_usd": budget_usd,
            })
            return {"ok": True}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def test_engine(self, engine_name: str) -> dict:
        try:
            engine = get_engine(engine_name)
            return engine.check()
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def fetch_jd(self, url: str) -> dict:
        try:
            jd = jd_fetcher.fetch_jd(url)
            return {"ok": True, "jd": jd}
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
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

        result["repeated_words"] = sanitizer.find_repeated_words(
            result["cv"], protected=keywords)
        result["ok"] = True
        return result

    def external_score(self, cv: str, jd: str) -> dict:
        if not _external_scorer_available:
            return {"ok": False, "error": "ats_resume_checker not installed (pip install ats-resume-checker)"}
        try:
            import tempfile, os
            with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
                f.write(cv)
                tmpfile = f.name
            try:
                result = _ext_analyzer.analyze_resume(tmpfile, jd)
                return {
                    "ok": True,
                    "ats_score": result.get("ats_score", 0),
                    "match_rate": result.get("match_rate", 0),
                    "matched_keywords": result.get("matched_keywords", []),
                    "missing_keywords": result.get("missing_keywords", []),
                    "suggestions": result.get("suggestions", []),
                }
            finally:
                os.unlink(tmpfile)
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def export_pdf(self, cv: str) -> dict:
        clean = sanitizer.remove_dashes(cv)
        if platform.system() == "Windows":
            desktop = os.path.join(os.environ.get("USERPROFILE", os.path.expanduser("~")), "Desktop")
        else:
            desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        out = os.path.join(desktop, f"tailored_cv_{int(time.time())}.pdf")
        try:
            export_pdf(clean, out)
            return {"ok": True, "path": out}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    index = os.path.join(here, "..", "web", "index.html")
    webview.create_window("CV Tailor", index, js_api=Api(),
                          width=1060, height=880, min_size=(760, 620))
    webview.start()
