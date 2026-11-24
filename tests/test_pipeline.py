import datetime

import insert_news
from lib import digest, embeddings
from lib.utils import Utility


class FakeDb:
    def __init__(self, missing=None, ranked=None):
        self.missing = missing or []
        self.ranked = ranked or []
        self.calls = []

    def find_rows_missing_embedding(self, date=None, limit=5000):
        self.calls.append(("missing", date))
        return self.missing

    def update_embeddings(self, updates):
        self.calls.append(("embeddings", len(updates)))
        return len(updates)

    def fetch_ranked_by_date(self, date, limit=None):
        return self.ranked

    def upsert_digest(self, date, result):
        self.calls.append(("digest", date, result["summary"]))

    def notify_news_updated(self, date):
        self.calls.append(("notify", date))


def test_build_records_includes_relevance_score():
    [record] = insert_news._build_records([{
        "date": "2025-03-01", "title": "Trump signs order", "description": "", "link": "https://a.com/1",
        "news_source": "a.com", "image_url": "",
    }])
    assert record["relevance_score"] > 0


def test_enrich_day_skips_unconfigured_steps_but_always_notifies(monkeypatch):
    monkeypatch.delenv("VOYAGE_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("DIGEST_PROVIDER", raising=False)
    db = FakeDb()
    insert_news.enrich_day(db, datetime.date(2025, 3, 1))
    assert db.calls == [("notify", datetime.date(2025, 3, 1))]


def test_enrich_day_runs_all_steps_in_order(monkeypatch):
    monkeypatch.setenv("VOYAGE_API_KEY", "k")
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    monkeypatch.setattr(embeddings, "embed_documents", lambda texts: [[0.0] * 1024 for _ in texts])
    monkeypatch.setattr(digest, "generate_digest",
                        lambda date, stories: {"summary": f"S {date}", "top_story_ids": [1], "model": "m"})
    day = datetime.datetime(2025, 3, 1, tzinfo=datetime.timezone.utc)
    db = FakeDb(missing=[{"id": 1, "title": "t", "description": "d"}], ranked=[{"id": 1, "title": "t"}])

    insert_news.enrich_day(db, day)

    d = datetime.date(2025, 3, 1)
    assert db.calls == [("missing", d), ("embeddings", 1), ("digest", d, "S 2025-03-01"), ("notify", d)]


def test_enrich_day_survives_digest_failure(monkeypatch):
    monkeypatch.delenv("VOYAGE_API_KEY", raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")

    def boom(date, stories):
        raise digest.DigestError("refused")

    monkeypatch.setattr(digest, "generate_digest", boom)
    db = FakeDb(ranked=[{"id": 1, "title": "t"}])
    insert_news.enrich_day(db, datetime.date(2025, 3, 1))
    assert db.calls[-1][0] == "notify"


def test_date_range_keywords(monkeypatch):
    utils = Utility.__new__(Utility)  # skip the DB connection in __init__
    today = datetime.datetime.now(datetime.timezone.utc).date()
    assert utils.get_date_range("yesterday", "today") == (today - datetime.timedelta(days=1), today)
    assert utils.get_date_range("2025-03-01", None) == (datetime.date(2025, 3, 1),) * 2
    assert utils.get_date_range("2025-03-02", "2025-03-01") == (None, None)


def test_today_is_utc_whatever_the_local_timezone(monkeypatch):
    # 23:30 on Nov 10 in UTC-5 (a naive local now()) is already Nov 11 in UTC.
    moment = datetime.datetime(2026, 11, 11, 4, 30, tzinfo=datetime.timezone.utc)
    local = datetime.timezone(datetime.timedelta(hours=-5))

    class FakeDatetime(datetime.datetime):
        @classmethod
        def now(cls, tz=None):
            return moment.astimezone(tz) if tz else moment.astimezone(local).replace(tzinfo=None)

    import lib.utils as utils_module
    monkeypatch.setattr(utils_module.datetime, "datetime", FakeDatetime)
    assert utils_module.today_utc() == datetime.date(2026, 11, 11)


def test_image_repairer_skips_google_links_and_unreachable_images(monkeypatch):
    class Db:
        updated = None

        def find_rows_missing_image(self):
            return [
                (1, "https://news.google.com/rss/articles/CBMi123"),
                (2, "https://pub.test/ok"),
                (3, "https://pub.test/dead-image"),
                (4, "https://pub.test/no-image"),
            ]

        def update_images(self, updates):
            self.updated = sorted(updates)
            return len(updates)

    images = {"https://pub.test/ok": "https://img.test/ok.jpg", "https://pub.test/dead-image": "https://img.test/404.jpg"}
    fetched = []

    def fake_meta(url, session):
        fetched.append(url)
        return {"image": images.get(url, ""), "description": ""}

    monkeypatch.setattr(insert_news, "fetch_meta", fake_meta)
    monkeypatch.setattr(insert_news, "is_image_reachable", lambda image, referer, session: image.endswith("ok.jpg"))

    db = Db()
    assert insert_news.ImageRepairer(db, session=object()).run() == 1
    assert db.updated == [(2, "https://img.test/ok.jpg")]
    assert not any("google.com" in url for url in fetched)
