# `server/`

Express/TypeScript backend for user authentication (Google OAuth + email/password), backed by the same **Neon** Postgres database as the news scraper (a separate `users` table — see `db/schema.sql`). Run with `npm run dev` (via `ts-node-dev`) or built with `npm run build` (`tsc`). See the root [README.md](../README.md#install-and-start-server) for setup/env-var instructions.

## `server.ts`
Application entry point. Builds the Express app and wires up, in order: CORS (restricted to `CLIENT_URL`, credentials enabled), JSON/urlencoded body parsing, `express-session` (secret from `SECRET`, `secure` cookies in production, 24h `maxAge`), Passport (`initialize` + `session`), the `/api/auth` router from `auth.ts`, and a `GET /` health-check route. Exits at startup with an error if `CLIENT_URL` or `SECRET` aren't set. Listens on `PORT` (default `3001`).

## `auth.ts`
All authentication routes and Passport configuration, mounted at `/api/auth` by `server.ts`. Exits at startup if `GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET` aren't set.

-   **Google OAuth strategy** — on successful Google auth, upserts the user into the `users` table keyed on email (`INSERT ... ON CONFLICT (email) DO UPDATE`), using the profile's name/picture when available.
-   **`passport.serializeUser` / `deserializeUser`** — session stores just the user id; deserialization re-fetches the full row from Neon on each request.
-   **`GET /google`** — starts the Google OAuth flow (`passport.authenticate('google', ...)`).
-   **`GET /google/callback`** — OAuth callback; redirects to `CLIENT_URL + '/login'` on failure, or `CLIENT_URL` on success.
-   **`GET /user`** — returns `req.user` if authenticated, else `401`.
-   **`GET /logout`** — logs out, destroys the session, clears the `connect.sid` cookie, redirects to `CLIENT_URL`.
-   **`POST /login`** — email/password login: looks up the user by email, rejects if the account has no `password_hash` (social-login-only account), verifies the password with `bcrypt.compare`, then calls `req.login`.
-   **`POST /signup`** — hashes the password with `bcrypt` (cost 10) and inserts a new row into `users`; returns `400` on a Postgres unique-violation (`error.code === '23505'`, duplicate email).
-   **`GET /users`** — returns `id, email, name, profile_picture` for every user (no auth check — see Security notes below).

## `db.ts`
Creates and exports the shared `pg.Pool` (`DATABASE_URL`, with `ssl: { rejectUnauthorized: false }` since Neon requires TLS), used by `auth.ts`. Throws at import time if `DATABASE_URL` is missing.

## `hooks/userDb.ts`
An **in-memory** (`Map`)-backed user store — `findUserByEmail`, `findUserById`, `createUser`, `getAllUsers`. Not wired into `auth.ts` (which talks to Neon directly via `db.ts`) and not persistent across restarts; appears to be leftover scaffolding from before the Supabase/Neon integration was added, or a stub for tests.

## `express.d.ts` / `other-modules.d.ts`
TypeScript ambient type declarations — module/type augmentation so `express`, `passport`, etc. type-check correctly against this project's usage (e.g. `req.user`, `req.isAuthenticated()`).

## Security notes worth knowing about
These are pre-existing characteristics of the current code, not something introduced by this documentation pass — flagged here since they're not obvious from the file listing alone:

-   **`GET /users` has no authentication check** — any caller can list every user's id/email/name/profile picture.
-   **Every request/response in `auth.ts` is logged to stdout**, including email addresses on every login/signup attempt.
