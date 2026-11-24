"""Completeness check that runs on scraped articles before they're scored.

A missing description or image says nothing about how relevant a story is, so
lib/relevance.py doesn't look at it. Instead, every article that arrives without
one gets its page scraped again here (fetch_news_by_date already tried once, and
publisher pages fail transiently: timeouts, 429s, slow CDNs). Whatever is still
missing afterwards is reported, not penalized.

Google News redirect links can't be resolved to the article server-side, so
those are counted but not fetched.
"""

from concurrent.futures import ThreadPoolExecutor

from news_scraper import build_session, fetch_meta, is_google_link, is_image_reachable

REQUIRED_FIELDS = ("description", "image_url")

# Older rows stored this placeholder instead of an empty image_url.
_PLACEHOLDERS = {"", "no image available"}


def missing_fields(article):
    """The REQUIRED_FIELDS this article has no real value for, in order."""
    return [f for f in REQUIRED_FIELDS
            if (article.get(f) or "").strip().lower() in _PLACEHOLDERS]


def _refetch(article, session):
    """Scrape the article page again and fill whichever fields are still missing.
    Returns the fields it filled."""
    meta = fetch_meta(article["link"], session)
    filled = []
    missing = missing_fields(article)
    if "description" in missing and meta["description"]:
        article["description"] = meta["description"]
        filled.append("description")
    if "image_url" in missing and meta["image"] and \
            is_image_reachable(meta["image"], article["link"], session):
        article["image_url"] = meta["image"]
        filled.append("image_url")
    return filled


def complete(articles, session=None, workers=6):
    """Re-fetch missing descriptions and images in place; returns a summary dict:
    checked, incomplete, refetched, filled (per field), still_incomplete, unfetchable."""
    incomplete = [a for a in articles if missing_fields(a)]
    fetchable = [a for a in incomplete if a.get("link") and not is_google_link(a["link"])]

    filled = {f: 0 for f in REQUIRED_FIELDS}
    if fetchable:
        session = session or build_session()
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for fields in pool.map(lambda a: _refetch(a, session), fetchable):
                for f in fields:
                    filled[f] += 1

    summary = {
        "checked": len(articles),
        "incomplete": len(incomplete),
        "refetched": len(fetchable),
        "filled": filled,
        "still_incomplete": sum(1 for a in articles if missing_fields(a)),
        "unfetchable": len(incomplete) - len(fetchable),
    }
    if incomplete:
        print(f"🧩 {summary['incomplete']} of {summary['checked']} missing a description or image: "
              f"re-fetched {summary['refetched']}, filled {filled['description']} description(s) and "
              f"{filled['image_url']} image(s); {summary['still_incomplete']} still incomplete "
              f"({summary['unfetchable']} Google News link(s) can't be fetched)")
    return summary
