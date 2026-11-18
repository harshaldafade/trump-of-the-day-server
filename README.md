# News pipeline for trumpoftheday.com
 Scraper, relevance ranking, daily AI digest (free via OpenRouter, or Claude), and embeddings. Used as a git submodule of [divij-pawar/trump-of-the-day](https://github.com/divij-pawar/trump-of-the-day), whose `api/` serves this data to the site.

> **This repository is a data pipeline, not a server.** Despite the `-server` in its name, nothing here listens for requests. It is a batch job: once a day GitHub Actions runs it, it writes stories, a digest and embeddings to Postgres, and exits. The web server that the site talks to is the Fastify API in [`api/`](https://github.com/divij-pawar/trump-of-the-day/tree/main/api) of the main repository. The repository is due to be renamed to reflect this; until then, links and badges still use `trump-of-the-day-server`.

| Lives here (pipeline) | Lives in the main repo |
|---|---|
| Scraping, dedupe, relevance scoring | React website (`src/`) |
| Daily digest and embeddings | Fastify API that serves the data (`api/`) |
| Database schema and migrations (`db/`) | Terraform for GCP and AWS (`infra/`) |
| Daily GitHub Actions job and its Docker image | Website and API deploys |
 
![Docker Image Build](https://img.shields.io/github/actions/workflow/status/harshaldafade/trump-of-the-day-server/build-push.yml?label=Docker%20Image%20Build)
![Tests](https://img.shields.io/github/actions/workflow/status/harshaldafade/trump-of-the-day-server/test.yml?label=Tests)
![Daily News Update](https://img.shields.io/github/actions/workflow/status/harshaldafade/trump-of-the-day-server/daily-run.yml?label=Daily%20News%20Update)

## Documentation

Deeper reference docs live in [`docs/`](docs/):

-   [docs/scripts.md](docs/scripts.md) — every function/class in `news_scraper.py`, `insert_news.py`, `delete_news.py`, and what the `Dockerfile` does
-   [docs/lib.md](docs/lib.md) — `lib/utils.py` (the Neon database access layer), `lib/relevance.py`, `lib/digest.py` and `lib/embeddings.py`
-   [docs/db.md](docs/db.md) — the Neon schema (`db/schema.sql`), migrations, and the read-only-role gotcha
-   [CHANGELOG.md](CHANGELOG.md) — what changed, release by release
-   [docs/github.md](docs/github.md) — what each CI workflow, issue template, and policy file in `.github/` does

## Install
1. Create and activate virtual environment
```bash
$ python -m venv env
$ source env/bin/activate
```
2. Install dependencies
```bash
$ pip install -r requirements-dev.txt   # requirements.txt + pytest
```

3. Create an .env file
```
# Neon Postgres connection (owner role: the pipeline writes)
DATABASE_URL=<your neon connection string>
# Optional: daily digest (skipped if neither key is set; OpenRouter wins if both are)
OPENROUTER_API_KEY=          # free, via OpenRouter's Free Router (openrouter/free)
# OPENROUTER_MODELS=a/b:free,c/d:free   # pin specific free models instead of the router
ANTHROPIC_API_KEY=           # Claude; or force it with DIGEST_PROVIDER=anthropic
# ANTHROPIC_MODEL=claude-haiku-5-5      # ~$0.05/month instead of Opus
# Optional: embeddings for search / related coverage (skipped if unset)
VOYAGE_API_KEY=
```

4. Apply the schema: `db/schema.sql` for a new database, or the files in `db/migrations/` for an existing one (see [docs/db.md](docs/db.md)).

5. Run the tests
```bash
$ python -m pytest
```

## News Scraper
`news_scraper.py` pulls Trump-related news from two independent sources and merges/deduplicates the results:

-   **Google News RSS** (`news.google.com/rss/search`) — a lightweight, sanctioned feed endpoint. Its article links are Google redirect URLs that can't be resolved to the real article server-side, so entries from this source keep the Google link but have no thumbnail/description.
-   **[GDELT DOC 2.0 API](https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/)** (free, no API key) — the primary source; it returns real article URLs, direct thumbnails (`socialimage`), and has full historical coverage. GDELT asks for at least one request every 5 seconds, so the scraper enforces a 6-second minimum between its own requests automatically.

For each article missing a description, the scraper visits the real article page (skipping unresolvable Google links) to pull `og:description`/`twitter:description`/JSON-LD, filling in the thumbnail too if GDELT didn't supply one. All HTTP requests go through a session with retry/backoff on 429/5xx responses and a short fuse on plain connection failures.

There's no headless browser or Selenium/Chrome dependency — everything is plain HTTP.

## What happens after a day is inserted
Each article is scored by `lib/relevance.py` before insert (rows whose `link` is already stored are skipped). Then, for every processed date, `enrich_day` in `insert_news.py`:

1.  embeds new rows with Voyage (`voyage-3.5`, if `VOYAGE_API_KEY` is set) for semantic search and "related coverage";
2.  asks an LLM for a short neutral summary of the day's top 40 stories and its top five story ids, stored in `daily_digest`. By default this goes to OpenRouter's [Free Router](https://openrouter.ai/docs/guides/routing/routers/free-router) (`openrouter/free`, needs `OPENROUTER_API_KEY`), which picks an available free model; the model that actually wrote the brief is stored and shown on the site; with `DIGEST_PROVIDER=anthropic` it uses Claude (`ANTHROPIC_API_KEY`);
3.  sends `NOTIFY news_updated, '<date>'`, which makes every running API instance drop its cached copy of that date and push a WebSocket message to open browsers.

A failure in step 1 or 2 is logged and doesn't stop the others.

## Run insert script
The `insert_news` script fetches and stores news articles in the Neon
database for a given date range.

### Running the script

You can run the script directly from the command line:

``` bash
python insert_news.py [start_date] [end_date]
```

#### Arguments

-   `start_date` (optional):
    -   Accepts `YYYY-MM-DD` format.\
    -   You can also pass `today`/`t` or `yesterday`/`y`.\
    -   If not provided, defaults to today.
-   `end_date` (optional):
    -   Accepts `YYYY-MM-DD` format, or `today`/`t`.\
    -   If not provided, the utility will only fetch news for the
        `start_date`.

The Docker image (and so the daily GitHub Actions run) uses `yesterday today`: re-scraping yesterday picks up stories published after the previous day's run, and duplicates are skipped.

#### Examples

1.  Fetch news for **today**:

``` bash
python insert_news.py today
```

2.  Fetch news for a specific date:

``` bash
python insert_news.py 2025-09-10
```

3.  Fetch news for a date range:

``` bash
python insert_news.py 2025-09-01 2025-09-05
```

### Output

-   The script prints progress logs while fetching and saving articles.\
-   At the end, it shows the total number of articles saved.

Example output:

    🔍 Processing news from 2025-09-01 to 2025-09-05
    📊 Total articles saved: 120

If no news is fetched, you will see:

    ⚠️ No news fetched for 2025-09-10.

If there is an insertion error, you will see:

    ❌ Error inserting data for 2025-09-03: <error_message>

### Maintenance subcommands

`insert_news.py` also supports these maintenance operations:

-   **`backfill-missing`** — finds every date with zero rows between the table's earliest date and yesterday, scrapes all of them (capped at 15 articles/day to match the site's historical density), and inserts everything in a single bulk request rather than one insert per day.

    ``` bash
    python insert_news.py backfill-missing
    ```

-   **`repair-descriptions`** — finds existing rows with an empty `description` and a fetchable (non-Google) link, and re-visits each article page to fill one in. Rows behind a Google News redirect link are skipped since they can't be resolved server-side.

    ``` bash
    python insert_news.py repair-descriptions
    ```

-   **`enrich [start] [end]`** — re-runs embeddings, the daily digest and the `NOTIFY` for a date or range without scraping (e.g. to regenerate digests after changing the prompt).

    ``` bash
    python insert_news.py enrich 2025-09-01 2025-09-05
    ```

-   **`backfill-embeddings`** — embeds every row that has no embedding yet, 1,000 at a time. Run once after migration 002.

-   **`rescore [start] [end]`** — recomputes `relevance_score` for existing rows (all rows if no range). Run once after migration 002, and after changing `lib/relevance.py`.

All of them are safe to re-run at any time — they only ever act on rows that still need it (or overwrite with the same result).

## Run delete script
The `delete_news` script deletes news articles from the Neon database
for a given date range.

### Running the script

You can run the script directly from the command line:

``` bash
python delete_news.py [start_date] [end_date] [--force]
```

#### Arguments

-   `start_date` (optional):
    -   Accepts `YYYY-MM-DD` format.\
    -   You can also pass `today` or `t` to delete news for the current
        date.\
    -   If not provided, the utility will use its default logic.
-   `end_date` (optional):
    -   Accepts `YYYY-MM-DD` format.\
    -   If not provided, the utility will only delete news for the
        `start_date`.
-   `--force`, `-f`, `yes`, or `y` (optional):
    -   Skips the confirmation prompt and directly deletes the articles.

#### Examples

1.  Delete news for **today** (with confirmation prompt):

``` bash
python delete_news.py today
```

2.  Delete news for a specific date (without confirmation prompt):

``` bash
python delete_news.py 2025-09-10 --force
```

3.  Delete news for a date range:

``` bash
python delete_news.py 2025-09-01 2025-09-05
```

#### Confirmation Prompt

If `--force` is not passed, you will see a prompt:

    ⚠️ You are about to delete all news articles from 2025-09-01 to 2025-09-05
    Are you sure you want to proceed? (yes/no): 

Type `yes` to proceed, or anything else to cancel.

### Output

-   The script prints logs while deleting articles.\
-   At the end, it shows the total number of articles deleted.

Example output:

    🗑️ Deleting news from 2025-09-01 to 2025-09-05
    📊 Total articles deleted: 45

If no news is found for a date, you will see:

    ℹ️ No news articles found for 2025-09-10

If there is a deletion error, you will see:

    ❌ Error deleting data for 2025-09-03: <error_message>

