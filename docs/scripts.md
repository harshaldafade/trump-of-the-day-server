# Root scripts

Function/class-level reference for every Python script in the repo root. For day-to-day CLI usage of `insert_news.py`/`delete_news.py`, see the main [README.md](../README.md) — this page is the API-level companion to that, plus coverage for `news_scraper.py`, `sort-news.py`, and `deepseek-test.py`, which the main README doesn't detail.

---

## `news_scraper.py`

Fetches Trump-related news from Google News RSS and the GDELT DOC 2.0 API, merges/deduplicates, and enriches with real descriptions/thumbnails. See the main README's [News Scraper](../README.md#news-scraper) section for the source-selection rationale; this section documents each function.

#### `build_session()`
Returns a `requests.Session` with a random `User-Agent` (from `USER_AGENTS`) and automatic retry/backoff: up to 4 retries on `429/500/502/503/504` (`backoff_factor=1.5`, honors `Retry-After`), but only 1 retry on plain connection failures so an unreachable host fails fast instead of burning the full backoff budget.

#### `polite_sleep(base=0.4, jitter=0.6)`
Sleeps `base + random() * jitter` seconds — randomized so requests don't land in an easily-throttled fixed pattern.

#### `is_google_link(link)`
Returns `True` if `link`'s host ends in `google.com`. Google News RSS `<link>` values are obfuscated redirect IDs that return `400` or land on a generic Google page when fetched directly (confirmed by testing) rather than resolving to the real article, so this flags links that can't be scraped for a thumbnail/description.

-   **Usage:** `if not is_google_link(article["link"]): ...`

#### `fetch_meta(url, session)`
Visits a real article page and scrapes `og:image`/`twitter:image` and `og:description`/`twitter:description`/`meta[name=description]`, falling back to JSON-LD (`<script type="application/ld+json">`) for whichever field is still missing.

-   **Returns:** `{"image": str, "description": str}` (empty strings on any failure — never raises)

#### `fetch_google_news(target_date, session)`
Queries `news.google.com/rss/search` for `Donald Trump after:{date} before:{date+1}` and parses the RSS feed with `feedparser`. Splits each entry's title on `" - "` to separate headline from source name. Description/image are always empty here (Google's RSS `<summary>` is just the title+source repeated as HTML, and the link can't be resolved server-side — see `is_google_link`); `fetch_news_by_date` fills these in later where possible.

-   **Returns:** `list[dict]` — each with `title`, `link`, `description` (`""`), `news_source`, `image_url` (`""`), `date`

#### `fetch_gdelt_news(target_date, session)`
Queries the GDELT DOC 2.0 API (`mode=artlist`, `sourcelang:english`, `maxrecords=250`) for the given day. Enforces `GDELT_MIN_INTERVAL` (6s) between calls via a module-level timestamp, since GDELT's HTTPS endpoint silently stalls the TLS handshake (rather than returning a clean `429`) if you exceed its documented 1-request-per-5-seconds limit. Uses `http://` not `https://` — GDELT's HTTPS endpoint was found to be unreliable independent of rate limiting; plain HTTP is fine since this is a public, read-only, non-sensitive query.

-   **Returns:** `list[dict]` — each with `title`, `link` (real article URL), `description` (`""`, GDELT doesn't provide one), `news_source` (domain), `image_url` (GDELT's `socialimage`, may be empty), `date`

#### `fetch_news_by_date(target_date, daily_cap=None)`
The main entry point. Calls `fetch_gdelt_news` then `fetch_google_news`, deduplicating by link and by normalized title (GDELT wins ties since it's queried first and has real links/images). If `daily_cap` is set, sorts so image-bearing entries sort first (stable, so each source's own ordering is preserved within that split) and truncates to `daily_cap`. Finally, for every remaining article with a real (non-Google) link, fetches `fetch_meta` concurrently (`ThreadPoolExecutor(max_workers=6)`) to fill in `description` (always) and `image_url` (only if still empty) — safe to parallelize since it spreads across many different publisher domains rather than hammering one service.

-   **Args:** `target_date` (timezone-aware `datetime`); `daily_cap` (`int | None`) — cap the per-day article count (used by `MissingDaysBackfiller`, not by the normal daily `insert_news.py` flow)
-   **Returns:** `list[dict]` — `title`, `link`, `description`, `news_source`, `image_url`, `date` (`"YYYY-MM-DD"`)
-   **Usage:**
    ```python
    from datetime import datetime, timezone
    articles = fetch_news_by_date(datetime(2025, 9, 1, tzinfo=timezone.utc), daily_cap=15)
    ```

---

## `insert_news.py`

#### `_build_records(articles)`
Module-level helper shared by `NewsStorage` and `MissingDaysBackfiller`: converts `fetch_news_by_date`'s article dicts into rows shaped for `DatabaseConnection.insert_records` (adds a shared `created_at` timestamp).

#### `NewsStorage`
Fetches and stores news for a date or date range — the class behind the default (no-subcommand) CLI usage documented in the main README.

-   **`save_news_by_date(target_date)`** — fetches one day via `fetch_news_by_date` (no cap) and bulk-inserts. Returns the number of rows saved (`0` on no results or an insert error, logged either way).
-   **`run(start_date_str=None, end_date_str=None)`** — resolves the date range via `Utility.get_date_range`, then calls `save_news_by_date` for each day via `Utility.process_date_range` (2s delay between days). Prints a running total.

#### `MissingDaysBackfiller`
Replaces the old standalone `backfill_missing_news.py` script. `DAILY_CAP = 15`, matching the site's historical density.

-   **`run()`** — finds every zero-row date via `DatabaseConnection.find_missing_dates()`, scrapes **all** of them (`fetch_news_by_date(..., daily_cap=15)`) into one in-memory list, then inserts everything in a **single** `insert_records` call — bulk-scrape-then-bulk-ingest rather than one insert per day. A per-day scrape failure is logged and skipped; it doesn't abort the run.
-   **Usage:** `python insert_news.py backfill-missing`

#### `DescriptionRepairer`
Replaces the old standalone `backfill_descriptions.py` script. `WORKERS = 10`.

-   **`run()`** — finds candidate rows via `DatabaseConnection.find_rows_missing_description()`, fetches each concurrently via `fetch_meta` (skipping Google-redirect links via `is_google_link`), and bulk-updates via `DatabaseConnection.update_descriptions()`. Rows where no description could be found (dead links, paywalls, sites without OG/JSON-LD tags) are left untouched.
-   **Usage:** `python insert_news.py repair-descriptions`

---

## `delete_news.py`

#### `NewsDeletion`
-   **`delete_news_by_date(target_date)`** — deletes all rows for one date via `DatabaseConnection.delete_by_date`.
-   **`run(start_date_str=None, end_date_str=None, confirm=False)`** — resolves the date range, prompts for `yes`/`no` confirmation unless `confirm=True`, then deletes each day in the range via `Utility.process_date_range`.

**CLI note:** the force flag (`--force`/`-f`/`yes`/`y`) is parsed independently of position, so `python delete_news.py 2025-09-10 --force` (a single date plus the flag, no end date) works correctly — this was previously a bug where `--force` was assumed to always be `argv[3]`, so a single-date-plus-flag invocation was misparsed as `end_date="--force"` and crashed.

---

## `sort-news.py`

Standalone ranking-refresh script — fetches every row from a `news_articles` table (note: a different table name than `news`, which is what `insert_news.py`/`delete_news.py` operate on; this script predates or is independent of that table's current usage), scores each with `lib.equation.RankingEquation`, and writes the resulting `final_score` back to an `article_score` column.

-   **`fetch_articles_from_database()`** — `DatabaseConnection("news_articles").fetch_records(limit=1000)`.
-   **`update_article_scores_in_database(sorted_articles)`** — calls `DatabaseConnection.update_record(article.id, {"article_score": ...})` once per article (not batched — a candidate for the same `insert_records`/`update_descriptions`-style bulk treatment if this script sees regular use again).
-   **`main()`** — fetches, builds `RankingEquation` objects per row, calls `RankingEquation.rank_articles(...)` from `lib/equation.py` (briefly: computes uniqueness via TF-IDF cosine similarity, engagement from votes/shares/comments, exponential recency decay, source trust, content quality via readability/grammar, and a weighted final score), then persists the scores.

## `deepseek-test.py`

Ad-hoc scratch script, not part of any production flow: sends a hardcoded news excerpt to the DeepSeek chat API (`DSK_API_KEY` env var) asking for a 100-word summary, and prints the response. Useful as a minimal reference for wiring up an AI-summarization call if that "AI Summarize news" feature (listed in the main README's Features section) gets built out, but isn't invoked anywhere else in the codebase.

---

## `Dockerfile`

Builds the image `.github/workflows/build-push.yml` publishes and `daily-run.yml` runs on a schedule (see [github.md](github.md)). `python:3.12-slim` base; installs `libopenblas-dev`/`build-essential` (needed for SciPy/scikit-learn, pulled in by `lib/equation.py`'s dependencies even though the daily insert job itself doesn't use them) and `requirements.txt`; copies in only `insert_news.py`, `news_scraper.py`, and `lib/` (not `sort-news.py`, `delete_news.py`, or `server/`); default `CMD` is `python insert_news.py` (i.e. today's date, no arguments — the normal daily flow, not the `backfill-missing`/`repair-descriptions` subcommands).
