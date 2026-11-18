# `db/`

Neon Postgres schema for the news pipeline (writes, owner role) and the API in the parent repo (reads, `news_readonly` role).

## `schema.sql`
The full current schema, for a **new** database. Run once against the Neon owner connection string. Defines:

-   **`vector` extension** (pgvector).
-   **`news` table** — `id BIGSERIAL PRIMARY KEY`, `created_at`, `date DATE`, `title`, `description`, `link`, `news_source`, `image_url`, `relevance_score REAL` (`lib/relevance.py`), `embedding vector(1024)` (`lib/embeddings.py`). `link` is `UNIQUE` (`news_link_key`), which is what lets `insert_records` skip duplicates with `ON CONFLICT (link) DO NOTHING`. Indexed on `date` (every API query filters on it) and on `embedding` (HNSW, cosine distance) for search and related coverage.
-   **`daily_digest` table** — `date DATE PRIMARY KEY`, `summary TEXT`, `paragraphs JSONB`, `top_story_ids BIGINT[]`, `model TEXT`, `created_at`. One AI-written summary per day (`lib/digest.py`). `paragraphs` holds the same summary sentence by sentence with the news ids each sentence cites (`[[{"text", "story_ids"}]]`), or `NULL` when the model returned plain text.
-   **`news_readonly` role** (commented-out `CREATE ROLE` + active `GRANT` statements) — `SELECT` on `news` and `daily_digest`, used by the API. Important Neon-specific gotcha, also documented in the file: creating a role via the Neon Console/API/CLI automatically adds it to `neon_superuser`, granting `CREATEDB`/`CREATEROLE`/`BYPASSRLS` and effectively full read/write on every table — and that membership **cannot be revoked afterward**. Creating the role via plain SQL avoids this, since SQL-created roles get no elevated privileges by default. The explicit `GRANT`s are what define its access.

## `migrations/`
For an **existing** database, apply these in order instead of `schema.sql`. Each is idempotent.

-   **`002_dedupe_vector_digest.sql`** — enables pgvector; deletes duplicate rows that share a `link` (keeping the oldest), then adds the `news_link_key` unique constraint; adds the `date` index, `relevance_score` and `embedding` columns and the HNSW index; creates `daily_digest` (and adds its `paragraphs` column to a table created before citations existed) and grants `news_readonly` read access to it. The duplicate delete is destructive, so take a Neon branch first (`neon branches create --name pre-002`). Afterwards, run `python insert_news.py rescore` and `python insert_news.py backfill-embeddings` to fill the new columns for existing rows, and `python insert_news.py enrich <start> <end>` for digests on past days.

The `users` table from the removed Express auth server is no longer in `schema.sql`. Migration 002 doesn't drop it, since it may hold data; drop it by hand once you're sure it's unused.
