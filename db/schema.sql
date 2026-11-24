-- Neon schema for the news pipeline and the read-only API.
-- Fresh database: run this once against the Neon owner connection string.
-- Existing database: apply the files in db/migrations/ in order instead.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS news (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ,
    date DATE,
    title TEXT,
    description TEXT,
    link TEXT,
    news_source TEXT,
    image_url TEXT,
    relevance_score REAL,
    embedding vector(1024)
);

-- Dedupe on a hash of the link: some links are several KB, over btree's
-- index-row limit, so a plain UNIQUE (link) can't be built. Inserts use
-- ON CONFLICT (md5(link)) DO NOTHING.
CREATE UNIQUE INDEX IF NOT EXISTS news_link_md5_key ON news (md5(link));

CREATE INDEX IF NOT EXISTS news_date_idx ON news (date);
CREATE INDEX IF NOT EXISTS news_embedding_idx ON news USING hnsw (embedding vector_cosine_ops);

CREATE TABLE IF NOT EXISTS daily_digest (
    date DATE PRIMARY KEY,
    summary TEXT NOT NULL,
    -- The summary sentence by sentence, each with the news ids it cites:
    -- [[{"text": "...", "story_ids": [1, 2]}, ...], ...] (one inner list per
    -- paragraph). NULL when the model returned plain text without citations.
    paragraphs JSONB,
    top_story_ids BIGINT[] NOT NULL DEFAULT '{}',
    model TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Read-only role for the API (api/ in the parent repo).
--
-- IMPORTANT: create this via plain SQL, not the Neon Console/API/CLI.
-- Console/API/CLI-created roles are automatically added to `neon_superuser`,
-- which grants CREATEDB, CREATEROLE, BYPASSRLS, and effectively full read/write
-- on every table in the public schema -- roles created that way cannot be
-- scoped down afterward (ALTER ROLE / REVOKE membership requires ADMIN option
-- that not even the database owner has on a console-created role).
-- SQL-created roles get none of that by default, so an explicit GRANT here is
-- the actual privilege boundary.
--
-- CREATE ROLE news_readonly WITH LOGIN PASSWORD '<set your own>';
GRANT USAGE ON SCHEMA public TO news_readonly;
GRANT SELECT ON news, daily_digest TO news_readonly;
