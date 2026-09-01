# `db/`

Neon Postgres schema for both the news data path and `server/`'s user auth — everything in this repo runs against one Neon database.

## `schema.sql`
Run once against the Neon owner connection string to set up the database. Defines:

-   **`news` table** — `id BIGSERIAL PRIMARY KEY`, `created_at TIMESTAMPTZ`, `date DATE`, `title TEXT`, `description TEXT`, `link TEXT`, `news_source TEXT`, `image_url TEXT`. This is the table every script in the repo (`insert_news.py`, `delete_news.py`, `sort-news.py`, `lib/utils.py`) reads and writes via `DatabaseConnection`.
-   **`users` table** — `id UUID PRIMARY KEY DEFAULT gen_random_uuid()` (needs the `pgcrypto` extension, also created here), `email TEXT UNIQUE NOT NULL`, `name TEXT`, `profile_picture TEXT`, `password_hash TEXT`, `created_at TIMESTAMPTZ`. Used by `server/auth.ts` (Google OAuth + email/password login) via `server/db.ts`. `email` is unique so the Google-login upsert (`INSERT ... ON CONFLICT (email) DO UPDATE`) and the signup duplicate-email check (Postgres error code `23505`) both work correctly.
-   **`news_readonly` role** (commented-out `CREATE ROLE` + active `GRANT` statements) — a read-only role intended for the browser-facing frontend. The file calls out an important Neon-specific gotcha: creating a role via the Neon Console/API/CLI automatically adds it to `neon_superuser`, granting `CREATEDB`/`CREATEROLE`/`BYPASSRLS` and effectively full read/write on every table — and that membership **cannot be revoked afterward** (would need `ADMIN` option that not even the database owner has on a console-created role). Creating the role via plain SQL instead avoids this entirely, since SQL-created roles get no elevated privileges by default. The explicit `GRANT USAGE`/`GRANT SELECT` statements are what actually define the role's access boundary.
