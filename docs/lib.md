# `lib/`

## `utils.py`

Shared Neon Postgres access layer used by `insert_news.py` and `delete_news.py`. Two classes:

-   **`Utility`** — date-range parsing/validation and generic per-date looping, independent of any specific database operation.
-   **`DatabaseConnection`** — all actual SQL against the `news` table (or whichever table name is passed in).

Every `DatabaseConnection` method opens its own connection via `psycopg2.connect(DATABASE_URL)` (from `.env`) and closes it when the `with` block exits. Methods that operate on many rows (`insert_records`, `update_descriptions`) use a single connection/transaction for the whole batch rather than one per row — this matters once volumes get into the hundreds/thousands, both for speed and for not exhausting Neon's connection limit.

---

### `Utility`

#### `__init__(table_name)`
Creates a `DatabaseConnection` for `table_name` and stores it as `self.db`.

-   **Args:** `table_name` (str) — the table to operate on (e.g. `"news"`)
-   **Usage:**
    ```python
    utils = Utility(table_name="news")
    utils.db.fetch_records()
    ```

#### `get_date_range(start_date_str=None, end_date_str=None)`
Parses and validates a start/end date pair from CLI-style string arguments, defaulting sensibly when arguments are omitted.

-   **Args:**
    -   `start_date_str` — `"YYYY-MM-DD"`, `"today"`/`"t"`, or `None` (defaults to today)
    -   `end_date_str` — `"YYYY-MM-DD"` or `None` (defaults to `start_date`)
-   **Returns:** `(start_date, end_date)` as `datetime.date` objects, or `(None, None)` if the input is invalid or `start_date > end_date`
-   **Usage:**
    ```python
    start, end = utils.get_date_range("2025-09-01", "2025-09-05")
    ```

#### `format_date(date)`
Formats a `datetime.date` as `"YYYY-MM-DD"`.

-   **Usage:** `utils.format_date(datetime.date(2025, 9, 1))  # -> "2025-09-01"`

#### `process_date_range(start_date, end_date, operation_func, delay=1)`
Calls `operation_func(single_date)` once for every date in `[start_date, end_date]` inclusive, sleeping `delay` seconds between calls, and sums up the integer each call returns.

-   **Args:**
    -   `start_date`, `end_date` — `datetime.date`
    -   `operation_func` — callable taking one `datetime.date` and returning a count (e.g. `NewsStorage.save_news_by_date`)
    -   `delay` (float) — seconds to sleep between dates
-   **Returns:** Sum of every `operation_func` call's return value
-   **Usage:**
    ```python
    total = utils.process_date_range(start, end, storage.save_news_by_date, delay=2)
    ```

---

### `DatabaseConnection`

#### `__init__(table_name)`
Loads `.env`, reads `DATABASE_URL`, and raises `ValueError` if it's missing.

-   **Usage:** `db = DatabaseConnection(table_name="news")`

#### `insert_record(data)`
Inserts a single row.

-   **Args:** `data` (dict) — column name → value
-   **Returns:** `{"inserted": True}`
-   **Usage:**
    ```python
    db.insert_record({"date": "2025-09-01", "title": "...", "link": "..."})
    ```
-   **Note:** Prefer `insert_records` for anything beyond a handful of rows — this opens a fresh connection per call.

#### `insert_records(data_list)`
Inserts many rows in one connection/transaction via `psycopg2.extras.execute_values`.

-   **Args:** `data_list` (list[dict]) — all dicts must share the same keys
-   **Returns:** Number of rows inserted (`int`)
-   **Usage:**
    ```python
    db.insert_records([{"date": "2025-09-01", "title": "A", ...}, {"date": "2025-09-01", "title": "B", ...}])
    ```

#### `update_record(id, data)`
Updates one row by primary key.

-   **Args:** `id` — row id; `data` (dict) — column name → new value
-   **Returns:** Number of rows affected (`int`, 0 or 1)
-   **Usage:** `db.update_record(42, {"description": "New description"})`

#### `delete_record(id)`
Deletes one row by primary key.

-   **Args:** `id` — row id
-   **Returns:** Number of rows affected (`int`)
-   **Usage:** `db.delete_record(42)`

#### `delete_by_date(date)`
Deletes every row for a given date.

-   **Args:** `date` — `datetime.date` or `"YYYY-MM-DD"` string
-   **Returns:** Number of rows deleted (`int`)
-   **Usage:** `db.delete_by_date("2025-09-01")`

#### `fetch_records(limit=100, offset=0)`
Paginated `SELECT *`.

-   **Returns:** `list[dict]`
-   **Usage:** `db.fetch_records(limit=50, offset=100)`

#### `fetch_by_date(date)`
`SELECT *` filtered to one date.

-   **Args:** `date` — `datetime.date` or `"YYYY-MM-DD"` string
-   **Returns:** `list[dict]`
-   **Usage:** `db.fetch_by_date("2025-09-01")`

#### `find_missing_dates()`
Finds every date with **zero** rows between `MIN(date)` in the table and yesterday (via a `generate_series` anti-join). Used to detect gaps left by scraper outages, rate-limit failures, etc.

-   **Returns:** `list[datetime.date]`, ascending
-   **Usage:**
    ```python
    for day in db.find_missing_dates():
        print(f"no articles for {day}")
    ```
-   **Used by:** `insert_news.py`'s `MissingDaysBackfiller`

#### `find_rows_missing_description()`
Finds rows with an empty `description` whose `link` is at least plausibly fetchable — i.e. a real `http(s)://` URL that isn't a `google.com` redirect link (those can't be scraped server-side; see `news_scraper.is_google_link`).

-   **Returns:** `list[tuple]` — `(id, link, image_url)` per candidate row
-   **Usage:**
    ```python
    for row_id, link, image_url in db.find_rows_missing_description():
        ...  # re-fetch the article page and build an update
    ```
-   **Used by:** `insert_news.py`'s `DescriptionRepairer`

#### `update_descriptions(updates)`
Bulk-updates `description` and `image_url` for many rows in one connection/transaction.

-   **Args:** `updates` (list[tuple]) — `(id, description, image_url)` per row
-   **Returns:** Number of rows updated (`int`)
-   **Usage:**
    ```python
    db.update_descriptions([(42, "A real description", "https://example.com/img.jpg")])
    ```
-   **Used by:** `insert_news.py`'s `DescriptionRepairer`

#### Enrichment helpers
Added for relevance ranking, embeddings and the daily digest (migration 002). All take a `date` or `"YYYY-MM-DD"` where a date is involved.

-   **`fetch_ranked_by_date(date, limit=None)`** — `id, title, description, news_source, link` for one date, `relevance_score DESC NULLS LAST`. Input to the daily digest.
-   **`find_rows_missing_embedding(date=None, limit=5000)`** — `id, title, description` of rows with `embedding IS NULL`, optionally for one date.
-   **`update_embeddings(updates)`** — bulk-sets `embedding` from `(id, vector_literal)` tuples (`lib.embeddings.to_vector_literal`).
-   **`fetch_for_scoring(start_date=None, end_date=None)`** / **`update_relevance(updates)`** — read the columns `score_article` needs and bulk-write `(id, score)`.
-   **`upsert_digest(date, digest)`** — insert or replace the `daily_digest` row.
-   **`notify_news_updated(date)`** — `SELECT pg_notify('news_updated', date)`. The API LISTENs on this channel.

`insert_records` now ends in `ON CONFLICT (link) DO NOTHING RETURNING id` and returns how many rows were actually inserted, so re-running a day only adds what's new.

`Utility.get_date_range` also accepts `yesterday`/`y` as the start date and `today`/`t` as the end date.

---

## `relevance.py`

Heuristic relevance scoring. `score_article(article)` returns a float (roughly -3 to 8) from: "Trump" in the headline (+3) or only in the description (+1.5); administration keywords in the headline (+1.5); a reputable outlet domain or subdomain (+1.5); a description (+0.5) and image (+0.5); minus 3 for idioms like "trump card" (which are also removed before the name check), minus 1 for unresolvable Google redirect links, minus 0.5 for very short headlines. `rank(articles)` sorts best-first. Scores are stored in `news.relevance_score`; the API orders each day by it and the digest reads the top 40. Pure functions, covered by `tests/test_relevance.py`.

## `digest.py`, `digest_openrouter.py`, `digest_anthropic.py`

`digest.generate_digest(date, stories)` writes the daily brief with whichever provider `digest.provider()` picks: `DIGEST_PROVIDER` if set, otherwise OpenRouter if `OPENROUTER_API_KEY` is set, otherwise Anthropic if `ANTHROPIC_API_KEY` is. `digest.py` holds what both share: the system prompt, `build_prompt`, the JSON schema, `parse_json_text` (tolerates code fences and surrounding prose), and `validate`. The model returns the summary sentence by sentence, each sentence with the ids of the one to three stories that support it (`paragraphs`), plus up to five `top_story_ids`. `validate` drops citations and top ids for stories the model wasn't shown (the sentence stays, uncited), builds the plain `summary` from the sentences, and accepts a bare `{"summary": …}` from a model that ignores the schema, in which case `paragraphs` is `None`.

**`digest_openrouter.generate`** calls `https://openrouter.ai/api/v1/chat/completions` with `requests`, at $0. By default it sends `model: "openrouter/free"`, OpenRouter's [Free Router](https://openrouter.ai/docs/guides/routing/routers/free-router). The router picks a currently available free model at random from those that support the request's features (here, structured output), so there's no list of model ids to maintain. The response's `model` field (e.g. `upstage/solar-pro-3:free`) is the model that actually wrote the brief. It's stored in `daily_digest.model` and shown on the site. Setting `OPENROUTER_MODELS` pins specific free models instead: one id goes in `model`, several go in OpenRouter's `models` fallback list. It asks for a JSON schema response. If that attempt fails (a model rejects `response_format`, or returns prose), it retries once without it and relies on the prompt's "respond with only JSON". Reasoning is capped with `reasoning: {effort: "low", exclude: true}` and `max_tokens` is 8000: some free models think before answering, reasoning tokens count against `max_tokens`, and without the cap one spent its whole budget thinking and returned no answer.

**`digest_anthropic.generate`** asks Claude (`ANTHROPIC_MODEL`, default `claude-opus-5-5`) (effort `medium`) for a two-to-three paragraph neutral summary with per-sentence citations plus up to five top story ids, using structured output (a JSON schema) so the reply is always parseable. Only headlines and the scraped publisher descriptions are sent, and the system prompt tells the model to treat them as data. On models that support it, server-side refusal fallbacks (`fallbacks="default"`) are on, so a safety-classifier decline on violent or extremist news is retried on the API's default fallback model. `claude-haiku-5-5` (about $0.05/month here) doesn't support them, so they're left off for it. `parse_response` rejects refusals and truncated output.

## `embeddings.py`

`embed_documents(texts)` embeds with Voyage `voyage-3.5` (`input_type="document"`, 1024 dimensions) in batches of 128. `document_text(row)` is `title + "\n\n" + description`. The API embeds search queries with the same model (`input_type="query"`), so keep the model name in sync with `api/src/embeddings.ts` in the parent repo. Needs `VOYAGE_API_KEY`.
