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

---

## Other files in this directory

-   **`equation.py`** — `RankingEquation`, the article-ranking scoring model (sentiment, keywords, grammar, engagement, recency, legitimacy, etc.) used by `sort-news.py`. Not covered here since this page is scoped to `utils.py`; see [scripts.md](scripts.md#sort-newspy) for a summary alongside `sort-news.py`.
