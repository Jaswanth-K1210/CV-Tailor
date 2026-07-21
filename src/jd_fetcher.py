from __future__ import annotations

import re
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup


class FetchError(Exception):
    pass


_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"
    )
}

_GREENHOUSE_RE = re.compile(r"boards\.greenhouse\.io/([^/?#]+)")
_LEVER_RE = re.compile(r"(?:jobs\.lever\.co|lever\.co)/([^/?#]+)")
_ASHBY_RE = re.compile(r"jobs\.ashbyhq\.com/[^/?#]+/([^/?#]+)")
_WORKDAY_RE = re.compile(r"(?:wd5\.myworkdayjobs|myworkdayjobs\.com)/")


def clean_html(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "header", "footer", "noscript"]):
        tag.decompose()
    text = soup.get_text(separator=" ")
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        raise FetchError("no readable text found in page")
    return text


def _detect_ats(url: str) -> str | None:
    if _GREENHOUSE_RE.search(url):
        return "greenhouse"
    if _LEVER_RE.search(url):
        return "lever"
    if _WORKDAY_RE.search(url):
        return "workday"
    return None


def _fetch_greenhouse(url: str) -> str:
    m = _GREENHOUSE_RE.search(url)
    if not m:
        raise FetchError("could not parse Greenhouse URL")
    board = m.group(1)
    job_id = None
    pm = re.search(r"/(\d+)(?:\?|$|#)", url)
    if pm:
        job_id = pm.group(1)
    api_url = f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs"
    if job_id:
        api_url += f"/{job_id}"
    resp = requests.get(api_url, headers=_HEADERS, timeout=20)
    if resp.status_code != 200:
        raise FetchError(f"Greenhouse API returned status {resp.status_code}")
    data = resp.json()
    if job_id and "content" in data:
        return _clean_text(data["content"])
    if "jobs" in data:
        for job in data["jobs"]:
            desc = job.get("content", "")
            if desc:
                return _clean_text(desc)
    raise FetchError("no job content found in Greenhouse response")


def _fetch_lever(url: str) -> str:
    m = _LEVER_RE.search(url)
    if not m:
        raise FetchError("could not parse Lever URL")
    posting = m.group(1)
    api_url = f"https://api.lever.co/v0/postings/{posting}?mode=json"
    resp = requests.get(api_url, headers=_HEADERS, timeout=20)
    if resp.status_code != 200:
        raise FetchError(f"Lever API returned status {resp.status_code}")
    data = resp.json()
    desc = data.get("descriptionPlain") or data.get("description", "")
    if not desc:
        raise FetchError("no job content found in Lever response")
    return _clean_html(desc) if "<" in desc else desc


def _fetch_playwright(url: str) -> str:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise FetchError(
            "Playwright not installed. Run: pip install playwright && playwright install chromium"
        )
    text = ""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent=_HEADERS["User-Agent"],
            viewport={"width": 1280, "height": 900},
        )
        page = ctx.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=25000)
            page.wait_for_timeout(3000)
            content = page.content()
            text = clean_html(content)
        finally:
            browser.close()
    if not text:
        raise FetchError("no readable text found after rendering page")
    return text


def _fetch_simple(url: str) -> str:
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=20)
    except requests.RequestException as exc:
        raise FetchError(f"could not reach {url}: {exc}") from exc
    if resp.status_code != 200:
        raise FetchError(
            f"site returned status {resp.status_code}; paste the job description manually"
        )
    return clean_html(resp.text)


def _clean_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    return re.sub(r"\s+", " ", soup.get_text(separator=" ")).strip()


def fetch_jd(url: str) -> str:
    ats = _detect_ats(url)
    if ats == "greenhouse":
        try:
            return _fetch_greenhouse(url)
        except FetchError:
            pass
    if ats == "lever":
        try:
            return _fetch_lever(url)
        except FetchError:
            pass
    try:
        return _fetch_simple(url)
    except FetchError:
        pass
    try:
        return _fetch_playwright(url)
    except FetchError:
        pass
    raise FetchError(
        "could not fetch job description from this URL. "
        "Paste the job description manually."
    )
