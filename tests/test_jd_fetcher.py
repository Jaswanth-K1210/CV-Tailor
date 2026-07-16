import pytest

from src.jd_fetcher import clean_html, fetch_jd, FetchError


def test_clean_html_strips_scripts_and_collapses_whitespace():
    html = "<html><head><style>x{}</style></head><body><script>bad()</script>"\
           "<h1>Job</h1>  <p>Do   things</p></body></html>"
    out = clean_html(html)
    assert "bad()" not in out
    assert "x{}" not in out
    assert "Job" in out
    assert "Do things" in out


def test_clean_html_empty_raises():
    with pytest.raises(FetchError):
        clean_html("<html><body>   </body></html>")


def test_fetch_jd_non_200_raises(monkeypatch):
    class FakeResp:
        status_code = 403
        text = ""

    monkeypatch.setattr("src.jd_fetcher.requests.get", lambda *a, **k: FakeResp())
    with pytest.raises(FetchError):
        fetch_jd("https://example.com/job")


def test_fetch_jd_success(monkeypatch):
    class FakeResp:
        status_code = 200
        text = "<html><body><h1>Engineer</h1><p>Python role</p></body></html>"

    monkeypatch.setattr("src.jd_fetcher.requests.get", lambda *a, **k: FakeResp())
    out = fetch_jd("https://example.com/job")
    assert "Engineer" in out
    assert "Python role" in out
