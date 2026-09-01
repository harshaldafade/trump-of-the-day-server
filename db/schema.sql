-- Neon schema for both the news data path and server/ auth (users).
-- Run once against the Neon owner connection string.

CREATE TABLE IF NOT EXISTS news (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ,
    date DATE,
    title TEXT,
    description TEXT,
    link TEXT,
    news_source TEXT,
    image_url TEXT
);

-- Used by server/auth.ts (Google OAuth + email/password login).
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT UNIQUE NOT NULL,
    name TEXT,
    profile_picture TEXT,
    password_hash TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Read-only role for the browser-facing frontend.
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
GRANT SELECT ON news TO news_readonly;
