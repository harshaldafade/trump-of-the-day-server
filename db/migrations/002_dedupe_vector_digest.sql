-- Migration 002: dedupe constraint, date index, relevance score, pgvector embeddings,
-- and the daily_digest table. Safe to re-run.
--
-- Run against the Neon *owner* connection string:
--   psql "$OWNER_DATABASE_URL" -f db/migrations/002_dedupe_vector_digest.sql
--
-- The DELETE below removes duplicate rows (same link) that earlier re-runs of
-- insert_news.py created, keeping the oldest copy. Take a Neon branch first if
-- you want a restore point: neon branches create --name pre-002.

BEGIN;

CREATE EXTENSION IF NOT EXISTS vector;

DELETE FROM news a
USING news b
WHERE a.link = b.link
  AND a.id > b.id;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'news_link_key') THEN
    ALTER TABLE news ADD CONSTRAINT news_link_key UNIQUE (link);
  END IF;
END $$;

-- Every frontend/API query filters on date.
CREATE INDEX IF NOT EXISTS news_date_idx ON news (date);

-- Heuristic relevance (lib/relevance.py); the API orders each day by it.
ALTER TABLE news ADD COLUMN IF NOT EXISTS relevance_score REAL;

-- voyage-3.5 document embeddings of "title\n\ndescription" (lib/embeddings.py).
ALTER TABLE news ADD COLUMN IF NOT EXISTS embedding vector(1024);
CREATE INDEX IF NOT EXISTS news_embedding_idx ON news USING hnsw (embedding vector_cosine_ops);

-- One Claude-written summary per day (lib/digest.py).
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

-- For databases that created daily_digest before citations existed.
ALTER TABLE daily_digest ADD COLUMN IF NOT EXISTS paragraphs JSONB;

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'news_readonly') THEN
    GRANT SELECT ON daily_digest TO news_readonly;
  END IF;
END $$;

COMMIT;
