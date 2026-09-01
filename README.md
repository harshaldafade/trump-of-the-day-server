# Server for trumpoftheday.com
 Backend, scraper, ranking algorithm
 
![Docker Image Build](https://img.shields.io/github/actions/workflow/status/harshaldafade/trump-of-the-day-server/build-push.yml?label=Docker%20Image%20Build)
![Daily News Update](https://img.shields.io/github/actions/workflow/status/harshaldafade/trump-of-the-day-server/daily-run.yml?label=Daily%20News%20Update)

## Documentation

Deeper reference docs live in [`docs/`](docs/):

-   [docs/scripts.md](docs/scripts.md) — every function/class in `news_scraper.py`, `insert_news.py`, `delete_news.py`, `sort-news.py`, `deepseek-test.py`, and what the `Dockerfile` does
-   [docs/lib.md](docs/lib.md) — every function in `lib/utils.py` (the Neon database access layer), with usage examples
-   [docs/db.md](docs/db.md) — the Neon schema (`db/schema.sql`) and the read-only-role gotcha documented in it
-   [docs/server.md](docs/server.md) — the Express/Passport auth backend in `server/`
-   [docs/github.md](docs/github.md) — what each CI workflow, issue template, and policy file in `.github/` does

## Install Scraper and Ranking algorithm
1. Create and activate virtual environment
```bash
$ python -m venv env
$ source env/bin/activate
`` 
2. Install dependencies
```bash
$ pip install -r requirements.txt
```

3. Create an .env file for the Neon database connection
```
# Neon Postgres connection details
DATABASE_URL=<your neon connection string>
```

## News Scraper
`news_scraper.py` pulls Trump-related news from two independent sources and merges/deduplicates the results:

-   **Google News RSS** (`news.google.com/rss/search`) — a lightweight, sanctioned feed endpoint. Its article links are Google redirect URLs that can't be resolved to the real article server-side, so entries from this source keep the Google link but have no thumbnail/description.
-   **[GDELT DOC 2.0 API](https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/)** (free, no API key) — the primary source; it returns real article URLs, direct thumbnails (`socialimage`), and has full historical coverage. GDELT asks for at least one request every 5 seconds, so the scraper enforces a 6-second minimum between its own requests automatically.

For each article missing a description, the scraper visits the real article page (skipping unresolvable Google links) to pull `og:description`/`twitter:description`/JSON-LD, filling in the thumbnail too if GDELT didn't supply one. All HTTP requests go through a session with retry/backoff on 429/5xx responses and a short fuse on plain connection failures.

There's no headless browser or Selenium/Chrome dependency — everything is plain HTTP.

## Install and Start Server
The server is created using express js and uses the same Neon Postgres database as the news scraper (see `db/schema.sql`'s `users` table). In recent future, we plan to move hosting to an [EC2 Instance](https://aws.amazon.com/ec2/).

Install server
```bash
$ cd server
$ npm install
$ touch .env
```
Create env with following variables in server
```
DATABASE_URL=<your neon connection string>

GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=



GOOGLE_CALLBACK_URL=http://localhost:3001/api/auth/google/callback
CLIENT_URL=http://localhost:3000

PORT=3001

SECRET=
NODE_ENV=development  # for local development or 'production' for deploying

```
Run server
```bash
$ npx ts-node server.ts
```
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
    -   You can also pass `today` or `t` to fetch news for the current
        date.\
    -   If not provided, the utility will use its default logic.
-   `end_date` (optional):
    -   Accepts `YYYY-MM-DD` format.\
    -   If not provided, the utility will only fetch news for the
        `start_date`.

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

`insert_news.py` also supports two maintenance operations, each backed by its own class in the same file:

-   **`backfill-missing`** — finds every date with zero rows between the table's earliest date and yesterday, scrapes all of them (capped at 15 articles/day to match the site's historical density), and inserts everything in a single bulk request rather than one insert per day.

    ``` bash
    python insert_news.py backfill-missing
    ```

-   **`repair-descriptions`** — finds existing rows with an empty `description` and a fetchable (non-Google) link, and re-visits each article page to fill one in. Rows behind a Google News redirect link are skipped since they can't be resolved server-side.

    ``` bash
    python insert_news.py repair-descriptions
    ```

Both are safe to re-run at any time — they only ever act on rows that still need it.

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

## Features running on server
<ul>
<li>User authorization
<li>News Scraping
<li>Ranking Algorithm
<li>AI Summarize news
<li>Upvotes/Downvotes/Comments
</ul>
