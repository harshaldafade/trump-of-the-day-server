"""Heuristic relevance scoring for scraped articles.

Both sources are queried for "Donald Trump", which pulls in a long tail of
tangential matches (sports "trump card"s, obituaries, foreign-language reposts
that slipped through). Rather than dropping rows -- a hard keyword filter was
tried and would have deleted ~750 legitimate administration stories that don't
name him in the headline -- every article gets a score, the API orders each day
by it, and the daily digest only reads the top of the list.

The score judges content only: the headline, the description's text and the
outlet. Whether a story is missing its description or image is not a relevance
signal; lib/completeness.py checks for that before scoring and re-fetches what
it can.

Pure functions only, so this is cheap to unit test and to re-run over old rows.
"""

import re
import urllib.parse

_TRUMP_RE = re.compile(r"\btrump\b", re.IGNORECASE)
_ADMIN_RE = re.compile(
    r"\b(white house|administration|president(?:ial|cy)?|executive order|oval office|cabinet|"
    r"tariffs?|doge|pentagon|state department|attorney general|justice department|"
    r"supreme court|congress(?:ional)?|senate|house speaker|vance|maga|gop|republicans?|"
    r"democrat(?:s|ic)?|federal|homeland security|national guard|"
    # Cabinet and senior officials, who headline stories without naming him.
    r"hegseth|rubio|bessent|lutnick|noem|bondi|kash patel|gabbard|witkoff|kushner|"
    r"leavitt|homan|rfk jr|kennedy jr|stephen miller)\b",
    re.IGNORECASE,
)
# U.S. government by abbreviation. Case-sensitive so "us" the pronoun doesn't count;
# GDELT titles space out punctuation ("U . S .").
_US_GOV_RE = re.compile(r"(?<![A-Za-z])(?:U\s*\.\s*S\b\.?|USA?|ICE|FBI|CIA)(?![A-Za-z])")
# Policy fronts the administration drives. Every story already matched a "Donald
# Trump" query, so these mark the ones about his policies rather than passing mentions.
_POLICY_RE = re.compile(
    r"\b(iran(?:ian)?|ukrain(?:e|ian)|russia|putin|zelensk[yi]+|israel|gaza|netanyahu|china|xi jinping|"
    r"greenland|nato|sanctions|immigration|deportations?|border|trade deal|"
    r"election|midterms?|shutdown|national security)\b",
    re.IGNORECASE,
)
# Idioms and contexts where "trump" isn't the person. The verb only counts as
# "trumps" or "trumped up": "Trump the environmentalist" and "deny Trump the one
# thing" are about him, so the bare "trump the" isn't an idiom.
_FALSE_POSITIVE_RE = re.compile(
    r"\b(trump card|trumps (?:the|all|everything)|trumped up|obituar(?:y|ies)|"
    r"fantasy football|horoscope)\b",
    re.IGNORECASE,
)

# Outlets with original reporting; aggregators and SEO farms rank below them.
REPUTABLE_DOMAINS = frozenset({
    "apnews.com", "reuters.com", "nytimes.com", "washingtonpost.com", "wsj.com",
    "bloomberg.com", "npr.org", "bbc.com", "bbc.co.uk", "politico.com", "thehill.com",
    "cnn.com", "foxnews.com", "nbcnews.com", "cbsnews.com", "abcnews.go.com", "axios.com",
    "theguardian.com", "usatoday.com", "ft.com", "economist.com", "latimes.com",
    "pbs.org", "c-span.org", "whitehouse.gov", "cnbc.com", "aljazeera.com", "theatlantic.com",
    "time.com", "dw.com", "propublica.org", "csmonitor.com",
})
# The same outlets as Google News names them: its links are redirects, so for those
# rows the outlet is only known from news_source.
REPUTABLE_SOURCES = frozenset({
    "associated press", "ap news", "reuters", "new york times", "washington post",
    "wall street journal", "wsj", "bloomberg", "npr", "bbc", "bbc news", "politico", "hill",
    "cnn", "fox news", "nbc news", "cbs news", "abc news", "axios", "guardian", "usa today",
    "financial times", "economist", "los angeles times", "pbs", "pbs news", "c-span",
    "white house", "white house (.gov)", "cnbc", "al jazeera", "atlantic", "time",
    "time magazine", "dw", "dw.com", "propublica", "christian science monitor",
})


# Articles must score above this to be stored: at or below it, nothing in the
# headline, description or outlet ties the story to Trump or his administration.
MIN_SCORE = 0.0
# Only each day's best-ranked stories are stored; the site, brief and embeddings
# never reach further down than this.
KEEP_PER_DAY = 50


def is_relevant(score):
    return score > MIN_SCORE


def _domain(link):
    host = urllib.parse.urlparse(link or "").netloc.lower()
    return host[4:] if host.startswith("www.") else host


def _is_reputable(domain, news_source):
    if domain in REPUTABLE_DOMAINS or any(domain.endswith("." + d) for d in REPUTABLE_DOMAINS):
        return True
    name = (news_source or "").strip().lower()
    name = name[4:] if name.startswith("the ") else name
    return name in REPUTABLE_SOURCES or name.removeprefix("www.") in REPUTABLE_DOMAINS


def score_article(article):
    """Return a relevance score (higher is better, roughly -3.5..9) for one article dict
    with the scraper's keys: title, description, link, news_source."""
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
    elif _ADMIN_RE.search(description):
        score += 0.5
    if _US_GOV_RE.search(title):
        score += 1.0
    if _POLICY_RE.search(title):
        score += 1.0

    if _is_reputable(domain, article.get("news_source")):
        score += 1.5
    if len(title) < 25:
        # Very short headlines are mostly section fronts / video stubs.
        score -= 0.5
    return round(score, 2)


def rank(articles):
    """Articles sorted by score, best first; stable for ties."""
    return sorted(articles, key=score_article, reverse=True)
