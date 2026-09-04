# `.github/`

GitHub-specific configuration: issue/PR templates, security policy, and CI workflows.

## `workflows/build-push.yml`
**Trigger:** `push` to `main`

Builds the project's `Dockerfile` and pushes it to GitHub Container Registry as `ghcr.io/<repo>/daily-news-job:latest`. This is the image `daily-run.yml` later pulls and runs — any code change merged to `main` (scraper, `insert_news.py`, `lib/`) only takes effect in production once this workflow rebuilds the image.

-   **Job:** `build-and-push` (`ubuntu-latest`)
    1. Checkout repo
    2. Log in to `ghcr.io` (using the built-in `GITHUB_TOKEN`)
    3. `docker build` the image
    4. `docker push` it to `ghcr.io`

## `workflows/daily-run.yml`
**Trigger:** `schedule` (`0 14 * * *` — daily at 14:00 UTC) or manual `workflow_dispatch`

The actual production job: pulls the image `build-push.yml` published and runs it once, passing `DATABASE_URL` through as an environment variable so the container's `insert_news.py` (the image's `CMD`, see the root `Dockerfile`) can write to Neon.

-   **Job:** `run-docker` (`ubuntu-latest`)
    1. Log in to `ghcr.io`
    2. `docker pull` the latest image
    3. `docker run` it with `DATABASE_URL` injected

-   **⚠️ Known gotcha (documented in the file itself):** GitHub auto-disables `schedule` triggers after ~60 days of repository inactivity, and a new push does **not** re-enable it — re-enabling requires a manual click on the workflow's page in the Actions tab. If daily news stops updating, check for a "this scheduled workflow is disabled" banner there first.

## `ISSUE_TEMPLATE/config.yml`
Issue-chooser configuration. Sets `blank_issues_enabled: false` (forces reporters to pick a template below) and adds one external contact link, "📢 Questions & Discussions", pointing at the repo's GitHub Discussions tab.

## `ISSUE_TEMPLATE/bug_report.md`
Template for the "🐛 Bug Report" issue type. Prompts for: bug description, numbered repro steps, expected behavior, screenshots, system info (OS/browser/version), and any additional context/logs.

## `ISSUE_TEMPLATE/feature_request.md`
Template for the "✨ Feature Request" issue type (labeled `enhancement` automatically). Prompts for: the problem motivating the request, the desired solution, alternatives considered, and additional context/links.

## `ISSUE_TEMPLATE/custom.md`
Template for the "📝 Custom Issue" type — a catch-all for anything that doesn't fit the bug/feature molds. Prompts for: issue description, steps to reproduce/implement, and notes.

## `PULL_REQUEST_TEMPLATE.md`
Default PR description template. Prompts for: description, related issue (`Fixes #ISSUE_NUMBER`), a checklist (style guidelines followed / self-reviewed / tests added / docs updated), screenshots, and additional notes.

## `SECURITY.md`
Security policy. Asks that vulnerabilities be reported by opening a GitHub issue.
