"""Heuristic relevance scoring for scraped articles.

Both sources are queried for "Donald Trump", which pulls in a long tail of
tangential matches (sports "trump card"s, obituaries, foreign-language reposts
that slipped through). Rather than dropping rows -- a hard keyword filter was
tried and would have deleted ~750 legitimate administration stories that don't
name him in the headline -- every article gets a score, the API orders each day
by it, and the daily digest only reads the top of the list.

Pure functions only, so this is cheap to unit test and to re-run over old rows.
"""

import re
import urllib.parse

_TRUMP_RE = re.compile(r"\btrump\b", re.IGNORECASE)
_ADMIN_RE = re.compile(
    r"\b(white house|administration|president|executive order|oval office|cabinet|"
    r"tariffs?|doge|pentagon|state department|attorney general|justice department|"
    r"supreme court|congress|senate|house speaker|vance|maga|gop|republicans?)\b",
    re.IGNORECASE,
)
# Idioms and contexts where "trump" isn't the person.
_FALSE_POSITIVE_RE = re.compile(
    r"\b(trump card|trumps? (?:the|all|everything)|trumped up|obituar(?:y|ies)|"
    r"fantasy football|horoscope)\b",
    re.IGNORECASE,
)

# Outlets with original reporting; aggregators and SEO farms rank below them.
REPUTABLE_DOMAINS = frozenset({
    "apnews.com", "reuters.com", "nytimes.com", "washingtonpost.com", "wsj.com",
    "bloomberg.com", "npr.org", "bbc.com", "bbc.co.uk", "politico.com", "thehill.com",
    "cnn.com", "foxnews.com", "nbcnews.com", "cbsnews.com", "abcnews.go.com", "axios.com",
    "theguardian.com", "usatoday.com", "ft.com", "economist.com", "latimes.com",
    "pbs.org", "c-span.org", "whitehouse.gov",
})


def _domain(link):
    host = urllib.parse.urlparse(link or "").netloc.lower()
    return host[4:] if host.startswith("www.") else host


def score_article(article):
    """Return a relevance score (higher is better, roughly -3..8) for one article dict
    with the scraper's keys: title, description, link, news_source, image_url."""
    title = article.get("title") or ""
    description = article.get("description") or ""
    domain = _domain(article.get("link"))

    score = 0.0
    # Idioms are removed before the name check so "trump card" doesn't also earn
    # the bonus it's being penalized for.
    if _FALSE_POSITIVE_RE.search(title) or _FALSE_POSITIVE_RE.search(description):
        score -= 3.0
        title = _FALSE_POSITIVE_RE.sub("", title)
        description = _FALSE_POSITIVE_RE.sub("", description)
    if _TRUMP_RE.search(title):
        score += 3.0
    elif _TRUMP_RE.search(description):
        score += 1.5
    if _ADMIN_RE.search(title):
        score += 1.5

    if domain in REPUTABLE_DOMAINS or any(domain.endswith("." + d) for d in REPUTABLE_DOMAINS):
        score += 1.5
    if domain.endswith("google.com"):
        # Unresolvable redirect link: no description/image, and duplicates of
        # these stories usually exist from GDELT with real links.
        score -= 1.0

    if description:
        score += 0.5
    if article.get("image_url"):
        score += 0.5
    if len(title) < 25:
        # Very short headlines are mostly section fronts / video stubs.
        score -= 0.5
    return round(score, 2)


def rank(articles):
    """Articles sorted by score, best first; stable for ties."""
    return sorted(articles, key=score_article, reverse=True)
