import requests
import feedparser
import urllib.parse
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor
import json
import re
import random
import time
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

GOOGLE_NEWS_RSS_URL = "https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
GDELT_API_URL = "http://api.gdeltproject.org/api/v2/doc/doc"  # their HTTPS endpoint is unreliable; HTTP is fine for this public, read-only query
# GDELT asks for at least one request every 5s; going faster gets HTTPS connections
# silently stalled at the TLS handshake instead of a clean 429.
GDELT_MIN_INTERVAL = 6.0
_last_gdelt_request_at = 0.0

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.6778.204 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0",
]


def build_session():
    """Session with UA rotation and automatic retry/backoff on rate-limit/server errors."""
    session = requests.Session()
    retry = Retry(
        total=4,
        connect=1,  # a host that's simply unreachable won't come back in seconds; fail fast
        status=4,   # but keep the full backoff budget for real 429/5xx rate-limit signals
        backoff_factor=1.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "HEAD"],
        respect_retry_after_header=True,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update({
        "User-Agent": random.choice(USER_AGENTS),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    })
    return session


def polite_sleep(base=0.4, jitter=0.6):
    """Randomized delay so requests don't land in a predictable, easily-throttled pattern."""
    time.sleep(base + random.random() * jitter)


def _normalize_title(title):
    return re.sub(r"\s+", " ", title).strip().lower()


def is_google_link(link):
    """news.google.com redirect links can't be fetched server-side (they 400/land on a
    generic Google page instead of the article), so scraping OG tags off them just
    returns Google's own branding image, not the real thumbnail."""
    return urllib.parse.urlparse(link).netloc.endswith("google.com")


def fetch_meta(url, session):
    """Scrape OG/Twitter/JSON-LD image + description off a real article page.
    Neither Google News RSS nor GDELT provide an actual description, so this is
    the only way to get one."""
    result = {"image": "", "description": ""}
    try:
        r = session.get(url, timeout=6)
        if r.status_code != 200:
            return result
        soup = BeautifulSoup(r.text, "html.parser")

        for tag in ["og:image", "twitter:image"]:
            meta = soup.find("meta", property=tag)
            if meta and meta.get("content"):
                result["image"] = meta["content"]
                break

        for tag in ["og:description", "twitter:description"]:
            meta = soup.find("meta", property=tag) or soup.find("meta", attrs={"name": tag})
            if meta and meta.get("content"):
                result["description"] = meta["content"].strip()
                break
        if not result["description"]:
            meta = soup.find("meta", attrs={"name": "description"})
            if meta and meta.get("content"):
                result["description"] = meta["content"].strip()

        if result["image"] and result["description"]:
            return result

        # JSON-LD fallback for whichever of image/description is still missing
        ld_json_blocks = soup.find_all("script", type="application/ld+json")
        for block in ld_json_blocks:
            try:
                data = json.loads(block.text.strip())
                candidates = data if isinstance(data, list) else [data]
                for item in candidates:
                    if not isinstance(item, dict):
                        continue
                    if not result["image"] and "image" in item:
                        img = item["image"]
                        if isinstance(img, str):
                            result["image"] = img
                        elif isinstance(img, dict):
                            result["image"] = img.get("url", "")
                    if not result["description"] and isinstance(item.get("description"), str):
                        result["description"] = item["description"].strip()
            except Exception:
                continue
            if result["image"] and result["description"]:
                break

    except Exception:
        return result

    return result


def fetch_google_news(target_date, session):
    start = target_date.strftime("%Y-%m-%d")
    end = (target_date + timedelta(days=1)).strftime("%Y-%m-%d")
    query = urllib.parse.quote(f"Donald Trump after:{start} before:{end}")
    url = GOOGLE_NEWS_RSS_URL.format(query=query)
    print("🔍 Google News RSS:", url)

    try:
        resp = session.get(url, timeout=10)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"⚠️ Google News RSS request failed: {e}")
        return []

    feed = feedparser.parse(resp.content)
    articles = []

    for entry in feed.entries:
        raw_title = entry.get("title", "")
        # Google formats entries as "Headline - Source Name"
        if " - " in raw_title:
            title, news_source = raw_title.rsplit(" - ", 1)
        else:
            title, news_source = raw_title, entry.get("source", {}).get("title", "")

        # Google's RSS <summary> is just the title + source repeated as HTML, not a
        # real description, so it's not worth extracting.
        articles.append({
            "title": title.strip(),
            "link": entry.get("link", ""),
            "description": "",
            "news_source": news_source.strip(),
            "image_url": "",
            "date": target_date.strftime("%Y-%m-%d"),
        })

    return articles


def fetch_gdelt_news(target_date, session):
    global _last_gdelt_request_at

    elapsed = time.monotonic() - _last_gdelt_request_at
    if elapsed < GDELT_MIN_INTERVAL:
        time.sleep(GDELT_MIN_INTERVAL - elapsed)

    start = target_date.strftime("%Y%m%d") + "000000"
    end = target_date.strftime("%Y%m%d") + "235959"
    params = {
        # GDELT indexes global, multilingual coverage by default; restrict to English
        # to match Google News RSS's en-US scope.
        "query": '"Donald Trump" sourcelang:english',
        "mode": "artlist",
        "maxrecords": 250,
        "format": "json",
        "startdatetime": start,
        "enddatetime": end,
    }
    print("🔍 GDELT search:", start, "-", end)

    try:
        _last_gdelt_request_at = time.monotonic()
        resp = session.get(GDELT_API_URL, params=params, timeout=8)
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError) as e:
        print(f"⚠️ GDELT request failed: {e}")
        return []

    articles = []
    for item in data.get("articles", []):
        articles.append({
            "title": item.get("title", "").strip(),
            "link": item.get("url", ""),
            "description": "",
            "news_source": item.get("domain", ""),
            "image_url": item.get("socialimage") or "",
            "date": target_date.strftime("%Y-%m-%d"),
        })

    return articles


def fetch_news_by_date(target_date, daily_cap=None):
    session = build_session()
    news_list = []
    seen_links = set()
    seen_titles = set()

    # GDELT first: it gives real article URLs and direct thumbnails. Google RSS is
    # only added for stories GDELT missed, since its links can't be resolved to a
    # real article URL server-side (see is_google_link).
    for fetch_fn in (fetch_gdelt_news, fetch_google_news):
        try:
            articles = fetch_fn(target_date, session)
        except Exception as e:
            print(f"⚠️ {fetch_fn.__name__} failed: {e}")
            articles = []

        for article in articles:
            link = article["link"]
            norm_title = _normalize_title(article["title"])
            if not norm_title or link in seen_links or norm_title in seen_titles:
                continue
            seen_links.add(link)
            seen_titles.add(norm_title)
            news_list.append(article)

        polite_sleep(1.0, 1.5)

    if daily_cap is not None:
        # Prefer entries that already have a real (GDELT-sourced) image; within that,
        # keep each source's own relevance/recency ordering (stable sort).
        news_list.sort(key=lambda a: not bool(a["image_url"]))
        news_list = news_list[:daily_cap]

    # Visit the real article page for its description (neither source provides one)
    # and, where still missing, its thumbnail. Run concurrently since these hit many
    # different publisher domains, not a single service that could rate-limit us.
    needs_meta = [a for a in news_list if a["link"] and not is_google_link(a["link"])]
    if needs_meta:
        with ThreadPoolExecutor(max_workers=6) as pool:
            metas = pool.map(lambda a: fetch_meta(a["link"], session), needs_meta)
            for article, meta in zip(needs_meta, metas):
                if not article["image_url"]:
                    article["image_url"] = meta["image"]
                article["description"] = meta["description"]

    return news_list


if __name__ == "__main__":
    test_date = datetime(2025, 2, 23, tzinfo=timezone.utc)
    articles = fetch_news_by_date(test_date)
    for article in articles:
        print(article)
