import datetime

import pytest

import insert_news
from lib import live
from tests.test_pipeline import FakeDb


class FakeResponse:
    def __init__(self, payload, status=200):
        self.payload = payload
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def post(self, url, json=None, headers=None, timeout=None):
        self.calls.append((url, json, headers))
        return self.response


@pytest.fixture
def upstash(monkeypatch):
    monkeypatch.setenv("UPSTASH_REDIS_REST_URL", "https://redis.test/")
    monkeypatch.setenv("UPSTASH_REDIS_REST_TOKEN", "tok")


def test_announce_clears_the_cached_day_and_publishes_it(upstash):
    session = FakeSession(FakeResponse([{"result": 2}, {"result": 3}]))
    assert live.announce(datetime.date(2026, 11, 18), session=session) == 3

    [(url, body, headers)] = session.calls
    assert url == "https://redis.test/pipeline"
    # Key names shared with cacheKeys in api/src/app.ts of the main repo.
    assert body == [["DEL", "news:v2:2026-11-18", "latest-date:v1"], ["PUBLISH", "news_updated", "2026-11-18"]]
    assert headers == {"Authorization": "Bearer tok"}


def test_announce_raises_on_command_errors(upstash):
    session = FakeSession(FakeResponse([{"result": 0}, {"error": "WRONGPASS"}]))
    with pytest.raises(RuntimeError, match="WRONGPASS"):
        live.announce("2026-11-18", session=session)


def test_is_configured_needs_both_settings(monkeypatch):
    monkeypatch.delenv("UPSTASH_REDIS_REST_URL", raising=False)
    monkeypatch.setenv("UPSTASH_REDIS_REST_TOKEN", "tok")
    assert not live.is_configured()


def test_enrich_day_announces_after_notify_and_survives_failures(monkeypatch, upstash):
    monkeypatch.setattr(insert_news.embeddings, "is_configured", lambda: False)
    monkeypatch.setattr(insert_news.digest, "is_configured", lambda: False)
    announced = []

    def flaky_announce(day):
        announced.append(day)
        raise RuntimeError("redis down")

    monkeypatch.setattr(insert_news.live, "announce", flaky_announce)
    db = FakeDb()
    insert_news.enrich_day(db, datetime.date(2026, 11, 18))  # must not raise
    assert db.calls == [("notify", datetime.date(2026, 11, 18))]
    assert announced == [datetime.date(2026, 11, 18)]
