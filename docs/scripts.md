# Root scripts

Function/class-level reference for every Python script in the repo root. For day-to-day CLI usage of `insert_news.py`/`delete_news.py`, see the main [README.md](../README.md) — this page is the API-level companion to that, plus coverage for `news_scraper.py`, which the main README doesn't detail.

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

#### `_is_english_script(title)`
Returns `False` if `title` contains characters from a non-Latin script (Hebrew, Arabic, Cyrillic, Devanagari, Thai, CJK, Hangul). Backstop against GDELT's `sourcelang:english` and Google's `hl=en-US` both being best-effort, not a strict filter — real non-English articles do slip through occasionally. Deliberately does *not* also require "trump" literally in the title as a relevance filter (checked against the live DB: that would have dropped ~750 legitimate rows — e.g. headlines about the administration that don't name him directly — to catch one bad match).

#### `fetch_meta(url, session)`
Visits a real article page and scrapes `og:image`/`twitter:image` and `og:description`/`twitter:description`/`meta[name=description]`, falling back to JSON-LD (`<script type="application/ld+json">`) for whichever field is still missing. Parses `r.content` (raw bytes), not `r.text` — `requests` defaults to `ISO-8859-1` per the old HTTP spec when a page's `Content-Type` header omits a charset, which mangles UTF-8 curly quotes etc. even though the page is actually UTF-8; BeautifulSoup's own encoding detection (meta charset/BOM-aware) gets this right.

-   **Returns:** `{"image": str, "description": str}` (empty strings on any failure — never raises)

#### `is_image_reachable(image_url, referer, session)`
Confirms an `image_url` actually resolves (`HEAD`, falling back to a streamed `GET` if the server rejects `HEAD` with `405`/`403`) and that the response is really an image (`Content-Type` starts with `image/`). Sends `Referer: {referer}` (the article's own link) since some CDNs hotlink-block bare requests. Used to clear (not drop) dead thumbnails — GDELT's `socialimage` and older backfilled links do rot over time.

-   **Returns:** `bool` (`False` on any request exception — never raises)

#### `fetch_google_news(target_date, session)`
Queries `news.google.com/rss/search` for `Donald Trump after:{date} before:{date+1}` and parses the RSS feed with `feedparser`. Splits each entry's title on `" - "` to separate headline from source name. Description/image are always empty here (Google's RSS `<summary>` is just the title+source repeated as HTML, and the link can't be resolved server-side — see `is_google_link`); `fetch_news_by_date` fills these in later where possible.

-   **Returns:** `list[dict]` — each with `title`, `link`, `description` (`""`), `news_source`, `image_url` (`""`), `date`

#### `fetch_gdelt_news(target_date, session)`
Queries the GDELT DOC 2.0 API (`mode=artlist`, `sourcelang:english`, `maxrecords=250`) for the given day. Enforces `GDELT_MIN_INTERVAL` (6s) between calls via a module-level timestamp, since GDELT's HTTPS endpoint silently stalls the TLS handshake (rather than returning a clean `429`) if you exceed its documented 1-request-per-5-seconds limit. Uses `http://` not `https://` — GDELT's HTTPS endpoint was found to be unreliable independent of rate limiting; plain HTTP is fine since this is a public, read-only, non-sensitive query.

If the request still fails after `build_session()`'s own retry budget (~22s), GDELT has been observed to rate-limit/throttle harder than that can ride out — a daily cron has hours of slack, so it waits `GDELT_COOLDOWN_SECONDS` (75s) and retries the whole call, up to `GDELT_COOLDOWN_ATTEMPTS` (2) extra times, before finally giving up and returning `[]` for the day.

-   **Returns:** `list[dict]` — each with `title`, `link` (real article URL), `description` (`""`, GDELT doesn't provide one), `news_source` (domain), `image_url` (GDELT's `socialimage`, may be empty), `date`

#### `fetch_news_by_date(target_date, daily_cap=None)`
The main entry point. Calls `fetch_gdelt_news` then `fetch_google_news`, deduplicating by link and by normalized title (GDELT wins ties since it's queried first and has real links/images), dropping anything `_is_english_script` flags. If `daily_cap` is set, sorts so image-bearing entries sort first (stable, so each source's own ordering is preserved within that split) and truncates to `daily_cap`. For every remaining article with a real (non-Google) link, fetches `fetch_meta` concurrently (`ThreadPoolExecutor(max_workers=6)`) to fill in `description` (always) and `image_url` (only if still empty) — safe to parallelize since it spreads across many different publisher domains rather than hammering one service. Finally, every article that now has an `image_url` gets it verified with `is_image_reachable` (`ThreadPoolExecutor(max_workers=10)`); a dead link gets cleared to `""` rather than dropping the article.

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
Module-level helper shared by `NewsStorage` and `MissingDaysBackfiller`: converts `fetch_news_by_date`'s article dicts into rows shaped for `DatabaseConnection.insert_records` (adds a shared `created_at` timestamp and a `relevance_score` from `lib.relevance.score_article`), leaving out articles that score `relevance.MIN_SCORE` (0) or below, then keeping only each day's `relevance.KEEP_PER_DAY` (50) best-scored articles (ties in scrape order), and logging how many it skipped at each step. `trim_days(db)` applies the same per-day limit to stored rows (the `trim-days` subcommand). `prune_irrelevant(db)` applies the same threshold to stored rows (the `prune-irrelevant` subcommand).

#### `enrich_day(db, day)`
Post-insert steps for one date, run by `NewsStorage`, `MissingDaysBackfiller` and the `enrich` subcommand: (1) embed the day's top-ranked rows (`EMBED_TOP_PER_DAY`, 50 by default) that have no embedding yet via `lib.embeddings` (skipped without `VOYAGE_API_KEY`), (2) generate and upsert the daily digest, with per-sentence citations, from the day's top-ranked 40 stories via `lib.digest` (skipped when no provider key is set: `OPENROUTER_API_KEY` or `ANTHROPIC_API_KEY`), (3) `NOTIFY news_updated` so running API instances drop their cache for that date and push a WebSocket update. Steps 1 and 2 log and continue on failure; the NOTIFY always runs. Accepts a `date` or an aware `datetime`.

#### `rescore(db, start_date=None, end_date=None)` / `backfill_embeddings(db, batch=1000)`
One-off maintenance helpers behind the `rescore` and `backfill-embeddings` subcommands (see [cli.md](cli.md)). `backfill_embeddings` applies the same per-day limit as `enrich_day`, so it embeds each day's top `EMBED_TOP_PER_DAY` stories that lack a vector and then stops.

#### `NewsStorage`
Fetches and stores news for a date or date range — the class behind the default (no-subcommand) CLI usage documented in the main README.

-   **`save_news_by_date(target_date)`** — fetches one day via `fetch_news_by_date` (no cap), runs `lib.completeness.complete` to re-fetch any description or image that's still missing, then scores, keeps the day's top 50 and bulk-inserts them (skipping links already stored), then runs `enrich_day`. After the insert it calls `DatabaseConnection.trim_days(50, date)`, because re-scraping a day that's already stored (the daily run redoes yesterday) can push it past 50. Returns the number of *new* rows saved (`0` on no results or an insert error, logged either way). If GDELT contributed nothing for the day (every returned link is a Google redirect — GDELT's cooldown/retry in `fetch_gdelt_news` was exhausted), or nothing was fetched at all, the date is appended to `self.degraded_days` rather than raising, so a bad day doesn't stop the rest of a multi-day range.
-   **`run(start_date_str=None, end_date_str=None)`** — resolves the date range via `Utility.get_date_range`, then calls `save_news_by_date` for each day via `Utility.process_date_range` (2s delay between days). Prints a running total.

The CLI entry point (`python insert_news.py [start] [end]`) checks `storage.degraded_days` after `run()` and exits `1` if it's non-empty — a day silently falling back to Google-RSS-only (no images/descriptions) is a real failure worth a red workflow run, not a quiet success. This is the only path in the file that can fail the process; `MissingDaysBackfiller`/`DescriptionRepairer` always exit `0` since they're re-runnable maintenance tools, not the thing users watch for day-to-day health.

#### `MissingDaysBackfiller`
Replaces the old standalone `backfill_missing_news.py` script. `DAILY_CAP = 15`, matching the site's historical density.

-   **`run()`** — finds every zero-row date via `DatabaseConnection.find_missing_dates()`, scrapes **all** of them (`fetch_news_by_date(..., daily_cap=15)`) into one in-memory list, then inserts everything in a **single** `insert_records` call — bulk-scrape-then-bulk-ingest rather than one insert per day — and finally runs `enrich_day` for each backfilled date. A per-day scrape failure is logged and skipped; it doesn't abort the run.
-   **Usage:** `python insert_news.py backfill-missing`

#### `DescriptionRepairer`
Replaces the old standalone `backfill_descriptions.py` script. `WORKERS = 10`.

-   **`run()`** — finds candidate rows via `DatabaseConnection.find_rows_missing_description()`, fetches each concurrently via `fetch_meta` (skipping Google-redirect links via `is_google_link`), and bulk-updates via `DatabaseConnection.update_descriptions()`. Rows where no description could be found (dead links, paywalls, sites without OG/JSON-LD tags) are left untouched.
-   **Usage:** `python insert_news.py repair-descriptions`

#### `ImageRepairer`
Same shape as `DescriptionRepairer`, for thumbnails. `WORKERS = 10`.

-   **`run()`** — finds rows with an empty or `"No Image Available"` `image_url` and a non-Google link via `DatabaseConnection.find_rows_missing_image()`, takes the image `fetch_meta` finds on each article page, keeps it only if `is_image_reachable` confirms it loads as an image, and bulk-updates via `DatabaseConnection.update_images()`. Google News redirect links are skipped: newer ones (`CBMi…AU_yq…`) don't contain the article URL, so there's no page to read.
-   **Usage:** `python insert_news.py repair-images`

---

## `delete_news.py`

#### `NewsDeletion`
-   **`delete_news_by_date(target_date)`** — deletes all rows for one date via `DatabaseConnection.delete_by_date`.
-   **`run(start_date_str=None, end_date_str=None, confirm=False)`** — resolves the date range, prompts for `yes`/`no` confirmation unless `confirm=True`, then deletes each day in the range via `Utility.process_date_range`.

**CLI note:** the force flag (`--force`/`-f`/`yes`/`y`) is parsed independently of position, so `python delete_news.py 2025-09-10 --force` (a single date plus the flag, no end date) works correctly — this was previously a bug where `--force` was assumed to always be `argv[3]`, so a single-date-plus-flag invocation was misparsed as `end_date="--force"` and crashed.

---

---

## `Dockerfile`

Builds the image `.github/workflows/build-push.yml` publishes and `daily-run.yml` runs on a schedule (see [github.md](github.md)). `python:3.12-slim` base; installs `requirements.txt` (all wheels, so no compiler packages); copies in only `insert_news.py`, `news_scraper.py`, and `lib/` (not `delete_news.py` or `tests/`); runs as an unprivileged `pipeline` user. Default `CMD` is `python insert_news.py yesterday today` — re-scraping yesterday picks up stories published after the previous run, and duplicate links are skipped on insert.
