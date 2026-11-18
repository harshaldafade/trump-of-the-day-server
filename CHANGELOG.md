# Changelog

All notable changes to the news pipeline. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- Sentence-level citations: the digest schema asks for the summary as paragraphs of sentences, each with the ids of the one to three stories that support it. Stored in the new `daily_digest.paragraphs` JSONB column (added to `schema.sql` and to migration 002 with `ADD COLUMN IF NOT EXISTS`). Citations to stories the model wasn't shown are dropped; a plain `{"summary"}` reply is still accepted without citations.
- OpenRouter digests make up to three attempts (two structured, then plain), each re-routed, and a cut-off error names the model and its reasoning token count. With citations, some free models (seen: `liquid/lfm-3-1.7b:free`, `nvidia/nemotron-3.5-lightning:free`) ignore the reasoning cap and think until `max_tokens` in about a third of attempts.
- Free daily digest via OpenRouter (`lib/digest_openrouter.py`), using the [Free Router](https://openrouter.ai/docs/guides/routing/routers/free-router) (`openrouter/free`) by default. It picks an available free model that supports structured output; the model that actually served the request is stored in `daily_digest.model`. `OPENROUTER_MODELS` pins specific free models instead. Includes a JSON-schema request with a plain-prompt retry, and lenient JSON parsing. It's the default provider when `OPENROUTER_API_KEY` is set.
- Digest provider switch (`DIGEST_PROVIDER=openrouter|anthropic`) and `ANTHROPIC_MODEL` override. Claude moved to `lib/digest_anthropic.py`; refusal fallbacks are only sent to models that support them.
- Relevance scoring (`lib/relevance.py`): every article gets a `relevance_score` on insert; the API orders each day by it. `rescore` subcommand recomputes it for existing rows.
- Daily digest (`lib/digest.py`): an LLM writes a short neutral summary of the day's top 40 stories and picks up to five top stories, stored in the new `daily_digest` table. Skipped if no provider key is set.
- Embeddings (`lib/embeddings.py`): new rows are embedded with Voyage `voyage-3.5` into a pgvector column for semantic search and related coverage. `backfill-embeddings` subcommand for existing rows. Skipped if `VOYAGE_API_KEY` isn't set.
- `enrich` subcommand to re-run embeddings, digest and notification for a date range without scraping.
- `NOTIFY news_updated` after each processed day, so the API invalidates its cache and pushes a WebSocket update to open browsers.
- Migration `db/migrations/002_dedupe_vector_digest.sql`.
- `yesterday`/`y` start-date and `today`/`t` end-date keywords for `insert_news.py`.
- `pytest` suite (`tests/`) and a `test.yml` workflow; `requirements-dev.txt`; `pytest.ini`.
- `workflow_dispatch` trigger on `build-push.yml`.

### Changed
- Inserts skip links that are already stored (`ON CONFLICT (link) DO NOTHING`) and report how many rows were actually new. The table now has a `UNIQUE (link)` constraint and an index on `date`.
- The daily job runs `insert_news.py yesterday today` instead of only today, so stories published after the previous run's 14:00 UTC cut-off are picked up.
- `daily-run.yml` passes `OPENROUTER_API_KEY`, `ANTHROPIC_API_KEY` and `VOYAGE_API_KEY` (secrets) and `OPENROUTER_MODELS`, `DIGEST_PROVIDER` and `ANTHROPIC_MODEL` (variables) to the container.
- `requirements.txt` lists only direct dependencies (was a 59-package freeze including the ranking experiment's ML stack); the Docker image no longer installs compiler/BLAS packages and runs as a non-root user.
- `db/schema.sql` reflects the current schema; `news_readonly` gets `SELECT` on `daily_digest` too.
- The README states that this repository is a daily batch pipeline, not a server (the Express `server/` is gone; the site's API lives in the main repository's `api/`), and lists what lives here versus there. The repository will be renamed; links still use `trump-of-the-day-server` until then.

### Fixed
- `NewsStorage.save_news_by_date` crashed with `AttributeError` when recording a degraded day, because `process_date_range` passes `date` objects (which have no `.date()`).
- OpenRouter digests could come back empty: the free router can pick a reasoning model (seen: `nvidia/nemotron-3.5-super-vl:free`), whose reasoning tokens count against `max_tokens`. It spent all 4000 thinking and wrote no answer, on both attempts. Requests now send `reasoning: {effort: "low", exclude: true}` and `max_tokens: 8000`; found and verified with real calls against a local database.
- `today`/`yesterday` used the machine's local date, so outside UTC (e.g. US evenings) a manual run processed the wrong days. They now use the UTC date, matching the site and the API. GitHub's runners are on UTC, so the scheduled job was unaffected.

### Removed
- `server/` (Express/Passport auth backend): unused by the site and not deployed. Its `users` table is no longer in `schema.sql` but isn't dropped from existing databases.
- `sort-news.py` and `lib/equation.py` (unused ML ranking experiment, read a `news_articles` table that the pipeline doesn't write), replaced by `lib/relevance.py`.
- `deepseek-test.py` (scratch script that printed its API key), replaced by `lib/digest.py`.
- `docs/server.md`.
