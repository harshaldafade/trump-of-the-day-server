from types import SimpleNamespace

from news_scraper import _is_english_script, _normalize_title, fetch_meta, is_google_link


def test_normalize_title_collapses_whitespace_and_case():
    assert _normalize_title("  Trump   Signs\nOrder ") == "trump signs order"


def test_non_latin_scripts_are_rejected():
    assert _is_english_script("Trump signs order")
    assert _is_english_script("Trump’s “deal” — explained")
    assert not _is_english_script("Трамп подписал указ")
    assert not _is_english_script("特朗普签署命令")


def test_google_links():
    assert is_google_link("https://news.google.com/rss/articles/abc")
    assert not is_google_link("https://www.reuters.com/world/")


class FakeSession:
    def __init__(self, html, status=200):
        self.response = SimpleNamespace(status_code=status, content=html.encode("utf-8"))

    def get(self, url, timeout=None):
        return self.response


def test_fetch_meta_prefers_open_graph():
    html = """<html><head>
      <meta property="og:image" content="https://img/og.jpg">
      <meta property="og:description" content=" OG description ">
      <meta name="description" content="plain description">
    </head></html>"""
    assert fetch_meta("https://x", FakeSession(html)) == {"image": "https://img/og.jpg", "description": "OG description"}


def test_fetch_meta_falls_back_to_json_ld():
    html = """<html><head><script type="application/ld+json">
      {"@type": "NewsArticle", "image": {"url": "https://img/ld.jpg"}, "description": "LD description"}
    </script></head></html>"""
    assert fetch_meta("https://x", FakeSession(html)) == {"image": "https://img/ld.jpg", "description": "LD description"}


def test_fetch_meta_never_raises_on_bad_status():
    assert fetch_meta("https://x", FakeSession("", status=404)) == {"image": "", "description": ""}
