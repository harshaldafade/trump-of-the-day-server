# Command reference

Everything the pipeline can do from a terminal. Dates are `YYYY-MM-DD`, or `today`/`t` and `yesterday`/`y`, which are **UTC** dates: the same day boundary the site and API use, whatever your machine's timezone.

Run these from the repository root with the virtual environment active and `DATABASE_URL` set (see [setup.md](setup.md)). A variable already in your shell wins over `.env`, which is how you point a run at a throwaway database safely.

## `insert_news.py`: scrape and store

```bash
python insert_news.py [start_date] [end_date]
```

| Argument | Meaning |
|---|---|
| `start_date` | `YYYY-MM-DD`, `today`/`t` or `yesterday`/`y`. Defaults to today (UTC). |
| `end_date` | `YYYY-MM-DD` or `today`/`t`. If omitted, only `start_date` is processed. |

The Docker image, and so the daily GitHub Actions run, uses `yesterday today`: re-scraping yesterday picks up stories published after the previous run, and duplicates are skipped.

```bash
python insert_news.py today                        # one day
python insert_news.py 2025-09-10                   # a specific date
python insert_news.py 2025-09-01 2025-09-05        # a range
```

Each processed day is scored and inserted (rows whose link is already stored are skipped), then `enrich_day` embeds the new rows, writes the brief and announces the change. See [scripts.md](scripts.md) for the functions behind it.

**Output** is progress logs and, at the end, the total saved:

```text
🔍 Processing news from 2025-09-01 to 2025-09-05
📊 Total articles saved: 120
```

If nothing is fetched you'll see `⚠️ No news fetched for 2025-09-10.`, and an insert failure prints `❌ Error inserting data for 2025-09-03: <error_message>`.

## Maintenance subcommands

`insert_news.py` also takes these operations. **All of them are safe to re-run.** They only act on rows that still need it, or overwrite with the same result.

| Subcommand | What it does |
|---|---|
| `backfill-missing` | Finds every date with zero rows between the table's earliest date and yesterday, scrapes them (capped at 15 articles a day to match the site's historical density) and inserts everything in one bulk request. |
| `repair-descriptions` | Finds rows with an empty `description` and a fetchable (non-Google) link, and re-visits each article page to fill one in. Google News redirect links are skipped because they can't be resolved server-side. |
| `repair-images` | Finds rows with no thumbnail whose link is a real article page and takes the page's `og:image` (or Twitter card, or JSON-LD image), keeping it only if it actually loads as an image. The site shows a placeholder for Google redirect links. |
| `enrich [start] [end]` | Re-runs embeddings (the day's top `EMBED_TOP_PER_DAY`), the daily brief and the announcement for a date or range, without scraping. Use it to regenerate briefs after changing the prompt. |
| `backfill-embeddings` | Embeds each day's top `EMBED_TOP_PER_DAY` stories (50 by default, ranked by `relevance_score`) that have no embedding yet, 1,000 at a time. Run once after migration 002. It never removes existing embeddings, and `EMBED_TOP_PER_DAY=0` embeds every row. |
| `rescore [start] [end]` | Recomputes `relevance_score` for existing rows (all rows if no range). Run once after migration 002, and after changing `lib/relevance.py`. |

```bash
python insert_news.py backfill-missing
python insert_news.py repair-descriptions
python insert_news.py repair-images
python insert_news.py enrich 2025-09-01 2025-09-05
python insert_news.py backfill-embeddings
python insert_news.py rescore
```

`backfill-embeddings` calls Voyage, so it needs `VOYAGE_API_KEY`, and a Voyage account with a payment method for standard rate limits. Without one the limit is 3 requests a minute and the command stops at the first batch.

## `delete_news.py`: remove stories

```bash
python delete_news.py [start_date] [end_date] [--force]
```

| Argument | Meaning |
|---|---|
| `start_date` | `YYYY-MM-DD`, or `today`/`t`. |
| `end_date` | `YYYY-MM-DD`. If omitted, only `start_date` is deleted. |
| `--force`, `-f`, `yes`, `y` | Skip the confirmation prompt. |

```bash
python delete_news.py today                        # asks first
python delete_news.py 2025-09-10 --force           # no prompt
python delete_news.py 2025-09-01 2025-09-05        # a range
```

Without `--force` you'll see a prompt, and only `yes` proceeds:

```text
⚠️ You are about to delete all news articles from 2025-09-01 to 2025-09-05
Are you sure you want to proceed? (yes/no):
```

Output ends with the total deleted (`📊 Total articles deleted: 45`). A date with nothing stored prints `ℹ️ No news articles found for 2025-09-10`, and a failure prints `❌ Error deleting data for 2025-09-03: <error_message>`.

Deleting a day does not delete its `daily_digest` row.
