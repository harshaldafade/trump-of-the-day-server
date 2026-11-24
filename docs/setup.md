# Setup guide

How to set the pipeline up end to end: the database, your environment, the GitHub secrets, the Docker image, the daily schedule and the first production run. The rest of the system (API, site, cloud infrastructure) is set up in the main repository's [setup guide](https://github.com/divij-pawar/trump-of-the-day/blob/main/docs/setup.md); this page covers what belongs to the pipeline.

## What the pipeline needs

| Need | Why | Required |
|---|---|---|
| A **Postgres database with pgvector**, such as [Neon](https://neon.tech) | Stories, briefs and embeddings are stored here | Yes |
| **Python 3.12** | The version the Docker image and CI use | Yes, to run locally |
| An **OpenRouter** API key | The daily brief, written by a free model | No. Without it the brief is skipped. |
| A **Voyage AI** API key | Embeddings for search and related coverage | No. Without it search and related coverage have no data. |
| An **Upstash Redis** REST URL and token | Tells the production API a day changed | No. Pages then refresh when their cache expires. |
| An **Anthropic** API key | Writing the brief with Claude instead of a free model | No |
| A **GitHub** repository with Actions | Runs the job daily | For production |

Only the database is mandatory. Every enrichment step logs and continues when its key is missing, so the raw stories are always saved.

## 1. The database

1. Create a Neon project. The default role is the **owner**, and it's the one the pipeline uses.
2. Apply the schema:
   - **New database:** run `db/schema.sql` against the owner connection string. It enables `vector`, creates `news` and `daily_digest`, the indexes, and grants the read-only role access.
   - **Existing database:** apply the files in `db/migrations/` in order. Take a Neon branch first, because migration `002` deletes duplicate rows. Details in [db.md](db.md).
3. Create the read-only role the API will use, **with plain SQL, not the Neon console**:

   ```sql
   CREATE ROLE news_readonly WITH LOGIN PASSWORD '<long random password>';
   GRANT USAGE ON SCHEMA public TO news_readonly;
   GRANT SELECT ON news, daily_digest TO news_readonly;
   ```

   Roles created through the console, API or CLI are added to `neon_superuser`, which can't be revoked afterwards. See [db.md](db.md).

The API's connection string, built from `news_readonly`, is stored in Google Secret Manager by the main repository's setup. The pipeline never uses it.

## 2. Install and test locally

```bash
python -m venv env
source env/bin/activate
pip install -r requirements-dev.txt     # requirements.txt + pytest
python -m pytest                        # no network or database required
```

The tests fake every external client, so they pass on a machine with no keys.

## 3. Environment variables

Create a `.env` in the repository root (it's gitignored), or export these in your shell. A variable already in the shell wins over `.env`.

| Variable | Meaning |
|---|---|
| `DATABASE_URL` | **Owner** connection string. The pipeline writes, so it needs more than the API's read-only role. Required. |
| `OPENROUTER_API_KEY` | Writes the brief through OpenRouter's Free Router (`openrouter/free`). The default provider when set. |
| `OPENROUTER_MODELS` | Optional. Comma-separated model ids to use instead of the router, for example `a/b:free,c/d:free`. |
| `DIGEST_PROVIDER` | Set to `anthropic` to use Claude. |
| `ANTHROPIC_API_KEY` | Needed for Claude. |
| `ANTHROPIC_MODEL` | Claude model to use. Defaults to `claude-opus-5-5`; `claude-haiku-5-5` costs about $0.05 a month at this volume. |
| `VOYAGE_API_KEY` | Embeddings with `voyage-3.5`. Add a payment method in the Voyage dashboard for normal rate limits. |
| `EMBED_TOP_PER_DAY` | Optional. How many of each day's stories, ranked by `relevance_score`, get an embedding. Default `50`; `0` embeds everything. Lower-ranked stories stay in the feed but not in search or related coverage. |
| `UPSTASH_REDIS_REST_URL`, `UPSTASH_REDIS_REST_TOKEN` | From `terraform output` in the main repo's `infra/gcp`. Both must be set for the announcement to run. |

Only these are read by the pipeline. Anything else in an old `.env` (for example variables from the removed Express server) is ignored.

## 4. Run it

```bash
python insert_news.py yesterday today        # what the daily job runs
python insert_news.py 2026-11-17             # one specific day
```

For a first load of an existing archive, run these once, in order, with the owner `DATABASE_URL`:

```bash
python insert_news.py rescore                # relevance scores for old rows
python insert_news.py backfill-embeddings    # needs VOYAGE_API_KEY
python insert_news.py enrich 2026-11-01 2026-11-18   # briefs for past days
```

Every command is listed in [cli.md](cli.md). They're all safe to re-run.

### Against a throwaway database

The main repository's `docker compose up -d` starts Postgres with pgvector on `127.0.0.1:5432`, seeded with synthetic stories, plus Redis and an Upstash-compatible REST endpoint on `:8079`. Point the pipeline at them on the command line so it can't touch production even if `.env` holds the real values:

```bash
export DATABASE_URL=postgres://owner:owner@127.0.0.1:5432/news
export UPSTASH_REDIS_REST_URL=http://127.0.0.1:8079 UPSTASH_REDIS_REST_TOKEN=local-token
python insert_news.py yesterday today
python insert_news.py enrich 2026-11-13 2026-11-13
```

With the main repo's site running (`npm run dev`), open pages update as soon as a day is processed.

## 5. Production: GitHub Actions

Three workflows live in `.github/` ([github.md](github.md) has the detail):

| Workflow | Trigger | What it does |
|---|---|---|
| `test.yml` | Every push to `main` and every pull request | Runs `pytest` on Python 3.12. |
| `build-push.yml` | Push to `main` that changes the Dockerfile, `requirements.txt`, `insert_news.py`, `news_scraper.py` or `lib/**` | Builds the image and pushes `ghcr.io/<repo>/daily-news-job:latest`. |
| `daily-run.yml` ("Run Docker image for Daily News Job") | `0 14 * * *` (14:00 UTC), or run by hand | Pulls that image and runs `insert_news.py yesterday today` with your secrets. |

Code changes reach production only after `build-push.yml` rebuilds the image.

### Secrets and variables

In the repository, **Settings → Secrets and variables → Actions**:

| Kind | Name | Value |
|---|---|---|
| Secret | `DATABASE_URL` | The Neon **owner** connection string |
| Secret | `OPENROUTER_API_KEY` | For the brief |
| Secret | `VOYAGE_API_KEY` | Optional, for embeddings |
| Secret | `UPSTASH_REDIS_REST_URL` | `terraform output upstash_rest_url` in the main repo |
| Secret | `UPSTASH_REDIS_REST_TOKEN` | `terraform output -raw upstash_rest_token` |
| Secret | `ANTHROPIC_API_KEY` | Optional, only for Claude |
| Variable | `OPENROUTER_MODELS`, `DIGEST_PROVIDER`, `ANTHROPIC_MODEL` | Optional overrides |

For a $0 setup, set `DATABASE_URL`, `OPENROUTER_API_KEY` and `VOYAGE_API_KEY`. Add the two Upstash secrets once the API is deployed.

Secrets go on the **Secrets** tab. The deploy settings for the API (`GCP_*`) are variables in the *main* repository, not here.

### First production run

1. Make sure the database schema is current and the owner `DATABASE_URL` secret is set.
2. Push so `build-push.yml` publishes the image. Confirm the package exists under the repository's Packages.
3. In **Actions → "Run Docker image for Daily News Job" → Run workflow**, run it by hand once and read the log. You should see the day's articles saved, then the embedding, brief and announcement steps.
4. Check the site: the new day's brief and stories appear, and an open tab updates itself if the Upstash secrets are set.

## 6. Troubleshooting

| Symptom | Cause and fix |
|---|---|
| Scheduled runs stopped after about 60 days of no commits | GitHub disables scheduled workflows on inactive repositories, and a new push doesn't re-enable them. Open the workflow in the Actions tab and re-enable it. This happened once; the missing days were backfilled. |
| `RateLimitError` with "3 RPM and 10K TPM" from Voyage | The Voyage account has no payment method. Add one; embedding the whole archive costs a few cents. |
| No brief for a day | All attempts failed. Check the log, then run `enrich <date> <date>`. The next daily run also retries yesterday. |
| `DATABASE_URL is missing` | `.env` isn't loaded or the variable isn't set in the shell or workflow secrets. |
| Site doesn't update live | The Upstash secrets are unset, or the API instances aren't running or subscribed. The cache for that day is still deleted if the secrets are set. |
| Duplicate stories after a re-run | They aren't created: inserts skip existing links. If an old database has duplicates, migration `002` removes them. |
| A story has no image or description | Its link is a Google News redirect that can't be resolved server-side. The site shows a placeholder. |
| `index row size … exceeds btree version 4 maximum` | The database still has a plain unique index on `link`. Apply migration `002`, which replaces it with an index on `md5(link)`. |
