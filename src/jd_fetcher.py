import re

import requests
from bs4 import BeautifulSoup


class FetchError(Exception):
    pass


_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}


def clean_html(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "header", "footer", "noscript"]):
        tag.decompose()
    text = soup.get_text(separator=" ")
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        raise FetchError("no readable text found in page")
    return text


def fetch_jd(url: str, timeout: int = 20) -> str:
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=timeout)
    except requests.RequestException as exc:
        raise FetchError(f"could not reach {url}: {exc}") from exc
    if resp.status_code != 200:
        raise FetchError(
            f"site returned status {resp.status_code}; paste the job description manually"
        )
    return clean_html(resp.text)
