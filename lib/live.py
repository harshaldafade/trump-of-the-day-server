"""Tell the API that a day changed, through Redis (Upstash's REST API).

The API on Cloud Run subscribes to the Redis channel `news_updated`: each running
replica drops its cached copy of that day and pushes a WebSocket message to the
browsers connected to it. Because Cloud Run scales to zero, there may be no
replica listening, so the pipeline also deletes the cached response itself.
Otherwise an older day it backfilled could be served from cache for up to 24 hours.

The cache key names must match `cacheKeys` in api/src/app.ts of the main repo.

Configuration (both optional; skipped if unset):
  UPSTASH_REDIS_REST_URL    e.g. https://xxx.upstash.io (Terraform output in infra/gcp)
  UPSTASH_REDIS_REST_TOKEN
"""

import datetime
import os

import requests

CHANNEL = "news_updated"
NEWS_KEY = "news:v2:{date}"
LATEST_DATE_KEY = "latest-date:v1"


def is_configured():
    return bool(os.getenv("UPSTASH_REDIS_REST_URL") and os.getenv("UPSTASH_REDIS_REST_TOKEN"))


def announce(date, session=None):
    """Delete `date`'s cached API response and publish it on `news_updated`.

    Returns how many API replicas received the message (0 when none is running).
    """
    if isinstance(date, datetime.date):
        date = date.isoformat()
    session = session or requests
    response = session.post(
        os.environ["UPSTASH_REDIS_REST_URL"].rstrip("/") + "/pipeline",
        json=[
            ["DEL", NEWS_KEY.format(date=date), LATEST_DATE_KEY],
            ["PUBLISH", CHANNEL, date],
        ],
        headers={"Authorization": f"Bearer {os.environ['UPSTASH_REDIS_REST_TOKEN']}"},
        timeout=10,
    )
    response.raise_for_status()
    results = response.json()
    errors = [r["error"] for r in results if isinstance(r, dict) and "error" in r]
    if errors:
        raise RuntimeError(f"Upstash: {'; '.join(errors)}")
    return results[1].get("result", 0)
