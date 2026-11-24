import datetime as dt
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor

from lib import completeness, digest, embeddings, live
from lib.relevance import KEEP_PER_DAY, MIN_SCORE, is_relevant, score_article
from lib.utils import Utility, DatabaseConnection
from news_scraper import fetch_news_by_date, fetch_meta, build_session, is_google_link, is_image_reachable


def _build_records(articles):
    """Turn scraped article dicts into rows ready for DatabaseConnection.insert_records:
    articles that score MIN_SCORE or below (not about Trump at all) are dropped, then
    only each day's KEEP_PER_DAY best-scored are kept, ties in scrape order."""
    created_at = datetime.now(timezone.utc).isoformat()
    records = [{
        "created_at": created_at,
        "date": article["date"],
        "title": article["title"],
        "description": article["description"],
        "link": article["link"],
        "news_source": article["news_source"],
        "image_url": article["image_url"],
        "relevance_score": score_article(article),
    } for article in articles]
    relevant = [r for r in records if is_relevant(r["relevance_score"])]
    if len(relevant) < len(records):
        print(f"🚮 Skipped {len(records) - len(relevant)} of {len(records)} article(s) scoring {MIN_SCORE:g} or below")

    by_day = {}
    for r in relevant:
        by_day.setdefault(r["date"], []).append(r)
    kept = []
    for day_records in by_day.values():
        kept.extend(sorted(day_records, key=lambda r: r["relevance_score"], reverse=True)[:KEEP_PER_DAY])
    if len(kept) < len(relevant):
        print(f"🚮 Skipped {len(relevant) - len(kept)} article(s) outside their day's top {KEEP_PER_DAY}")
    return kept


def _as_date(value):
    """process_date_range passes datetime.date; the backfiller passes aware datetimes."""
    return value.date() if isinstance(value, datetime) else value


def enrich_day(db, day):
    """Post-insert steps for one date, each skipped if its API key isn't set:

    1. embed the day's best-ranked rows that don't have an embedding yet (Voyage;
       the top EMBED_TOP_PER_DAY, 50 by default)
    2. (re)write the daily digest from the day's top-ranked stories (Claude)
    3. tell running API instances so they drop their cache and push to browsers:
       Postgres NOTIFY (the AWS stack listens) and Redis pub/sub through Upstash
       (production on Cloud Run listens; skipped without UPSTASH_REDIS_REST_*)

    A failure in 1 or 2 is logged and doesn't stop the others -- the raw feed is
    still useful without a digest.
    """
    day = _as_date(day)

    if embeddings.is_configured():
        try:
            rows = db.find_rows_missing_embedding(date=day, top_n=embeddings.top_per_day())
            if rows:
                vectors = embeddings.embed_documents([embeddings.document_text(r) for r in rows])
                db.update_embeddings([
                    (r["id"], embeddings.to_vector_literal(v)) for r, v in zip(rows, vectors)
                ])
                print(f"🧭 Embedded {len(rows)} article(s) for {day}")
        except Exception as e:
            print(f"⚠️ Embedding failed for {day}: {e}")

    if digest.is_configured():
        try:
            stories = db.fetch_ranked_by_date(day, limit=digest.MAX_STORIES)
            if stories:
                result = digest.generate_digest(day.isoformat(), stories)
                db.upsert_digest(day, result)
                print(f"📝 Digest written for {day} ({len(result['top_story_ids'])} top stories)")
        except Exception as e:
            print(f"⚠️ Digest failed for {day}: {e}")

    try:
        db.notify_news_updated(day)
    except Exception as e:
        print(f"⚠️ NOTIFY failed for {day}: {e}")

    if live.is_configured():
        try:
            replicas = live.announce(day)
            print(f"📣 Announced {day} to {replicas} API replica(s)")
        except Exception as e:
            print(f"⚠️ Redis announce failed for {day}: {e}")


class NewsStorage:
    """Fetches and stores news for a given date or date range."""

    def __init__(self):
        self.utils = Utility(table_name="news")
        self.db = self.utils.db
        # Dates where GDELT (the only source with real images/descriptions) contributed
        # nothing, so the day's feed silently degraded to Google-RSS-only. Checked by
        # __main__ to fail the run loudly instead of reporting success on a degraded day.
        self.degraded_days = []

    def save_news_by_date(self, target_date):
        """
        Fetches and stores news for a specific date in the Neon database.

        Args:
            target_date: The date to fetch news for

        Returns:
            Number of articles saved
        """
        news = fetch_news_by_date(target_date)
        if not news:
            print(f"⚠️ No news fetched for {target_date}.")
            self.degraded_days.append(_as_date(target_date))
            return 0

        if all(is_google_link(a["link"]) for a in news):
            print(f"⚠️ GDELT contributed zero articles for {_as_date(target_date)} "
                  f"-- feed for this day has no images/descriptions")
            self.degraded_days.append(_as_date(target_date))

        completeness.complete(news)

        try:
            # Insert the whole day's articles in one connection/transaction instead
            # of one connection per row. Links already stored are skipped.
            inserted = self.db.insert_records(_build_records(news))
        except Exception as e:
            print(f"❌ Error inserting data for {target_date}: {e}")
            return 0

        print(f"💾 {inserted} new of {len(news)} scraped for {_as_date(target_date)}")
        # Re-scraping a day (the daily run redoes yesterday) can push it past the
        # limit; trim it back before the brief and embeddings are worked out.
        try:
            trimmed = self.db.trim_days(KEEP_PER_DAY, date=_as_date(target_date))
            if trimmed:
                print(f"🚮 Trimmed {trimmed} row(s) outside the day's top {KEEP_PER_DAY}")
        except Exception as e:
            print(f"⚠️ Trim failed for {_as_date(target_date)}: {e}")
        enrich_day(self.db, target_date)
        return inserted

    def run(self, start_date_str=None, end_date_str=None):
        """
        Main method to run the news storage process.

        Args:
            start_date_str: Optional start date (YYYY-MM-DD or 'today'/'t')
            end_date_str: Optional end date (YYYY-MM-DD)
        """
        try:
            start_date, end_date = self.utils.get_date_range(start_date_str, end_date_str)
            if not start_date or not end_date:
                return

            print(f"🔍 Processing news from {start_date} to {end_date}")

            # Small delay between days; GDELT's own 6s/request pacing is enforced
            # inside news_scraper.py regardless of this value.
            total_saved = self.utils.process_date_range(
                start_date,
                end_date,
                self.save_news_by_date,
                delay=2
            )

            print(f"📊 Total articles saved: {total_saved}")
            return total_saved

        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            return 0


class MissingDaysBackfiller:
    """Finds dates with zero rows and backfills them in a single bulk insert.

    Scraping happens for every missing day first, then everything is sent to the
    database in one request rather than day-by-day, so a large backfill doesn't
    turn into thousands of small round trips.
    """

    # Matches the site's historical ~10-15 articles/day density instead of the
    # scraper's raw 250+/day across both sources combined.
    DAILY_CAP = 15

    def __init__(self, db):
        self.db = db

    def run(self):
        missing_days = self.db.find_missing_dates()
        if not missing_days:
            print("✅ No missing days.")
            return 0

        print(f"📅 {len(missing_days)} missing day(s) to backfill")

        records = []
        for i, day in enumerate(missing_days, 1):
            print(f"[{i}/{len(missing_days)}] scraping {day} ...")
            target_date = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
            try:
                articles = fetch_news_by_date(target_date, daily_cap=self.DAILY_CAP)
                completeness.complete(articles)
                records.extend(_build_records(articles))
            except Exception as e:
                print(f"  ❌ scrape failed for {day}: {e}")

        if not records:
            print("⚠️ Nothing scraped, nothing to insert.")
            return 0

        print(f"📥 Inserting {len(records)} articles across {len(missing_days)} day(s) in one request...")
        count = self.db.insert_records(records)
        print(f"✅ Inserted {count} rows.")
        for day in missing_days:
            enrich_day(self.db, day)
        return count


class DescriptionRepairer:
    """Finds rows with no description and fetches one from the real article page.

    Only needed for rows inserted before fetch_meta() started scraping descriptions;
    new inserts already come with one. Rows behind a Google News redirect link can't
    be visited server-side, so they're skipped.
    """

    WORKERS = 10

    def __init__(self, db, session=None):
        self.db = db
        self.session = session or build_session()

    def _fetch_one(self, row):
        row_id, link, image_url = row
        if is_google_link(link):
            return None
        meta = fetch_meta(link, self.session)
        if not meta["description"]:
            return None
        return row_id, meta["description"], image_url or meta["image"]

    def run(self):
        rows = self.db.find_rows_missing_description()
        print(f"📋 {len(rows)} row(s) to repair")
        if not rows:
            return 0

        updates = []
        with ThreadPoolExecutor(max_workers=self.WORKERS) as pool:
            for i, result in enumerate(pool.map(self._fetch_one, rows), 1):
                if result:
                    updates.append(result)
                if i % 100 == 0:
                    print(f"  ...{i}/{len(rows)} processed, {len(updates)} descriptions found so far")

        print(f"📥 Updating {len(updates)} row(s) ({len(rows) - len(updates)} had no description available, e.g. dead/paywalled links)")
        count = self.db.update_descriptions(updates)
        print(f"✅ Updated {count} rows.")
        return count


class ImageRepairer:
    """Finds rows with no thumbnail and takes one from the article page's og:image
    (or Twitter card / JSON-LD), keeping it only if it actually loads as an image.

    Google News redirect links can't be resolved to the article server-side (newer
    ones don't even contain the article URL), so those rows are skipped; the site
    shows a placeholder for them.
    """

    WORKERS = 10

    def __init__(self, db, session=None):
        self.db = db
        self.session = session or build_session()

    def _fetch_one(self, row):
        row_id, link = row
        if is_google_link(link):
            return None
        image = fetch_meta(link, self.session)["image"]
        if not image or not is_image_reachable(image, link, self.session):
            return None
        return row_id, image

    def run(self):
        rows = self.db.find_rows_missing_image()
        print(f"🖼️ {len(rows)} row(s) without an image to check")
        if not rows:
            return 0

        updates = []
        with ThreadPoolExecutor(max_workers=self.WORKERS) as pool:
            for i, result in enumerate(pool.map(self._fetch_one, rows), 1):
                if result:
                    updates.append(result)
                if i % 100 == 0:
                    print(f"  ...{i}/{len(rows)} processed, {len(updates)} images found so far")

        print(f"📥 Updating {len(updates)} row(s) ({len(rows) - len(updates)} had no usable image, e.g. dead/paywalled pages)")
        count = self.db.update_images(updates)
        print(f"✅ Updated {count} rows.")
        return count


def rescore(db, start_date=None, end_date=None):
    """Recompute relevance_score for existing rows (all rows if no range given)."""
    rows = db.fetch_for_scoring(start_date, end_date)
    count = db.update_relevance([(r["id"], score_article(r)) for r in rows])
    print(f"✅ Rescored {count} rows.")
    return count


def prune_irrelevant(db):
    """Delete stored rows scoring MIN_SCORE or below, the ones _build_records now skips.
    Run after `rescore` so the scores are current."""
    deleted = db.delete_by_max_relevance(MIN_SCORE)
    print(f"🚮 Deleted {deleted} row(s) scoring {MIN_SCORE:g} or below.")
    return deleted


def trim_days(db):
    """Delete every row outside its day's top KEEP_PER_DAY, the ones _build_records
    now never inserts. Stories a daily brief cites are kept. Run after `rescore`."""
    deleted = db.trim_days(KEEP_PER_DAY)
    print(f"🚮 Deleted {deleted} row(s) outside their day's top {KEEP_PER_DAY}.")
    return deleted


def backfill_embeddings(db, batch=1000):
    """Embed each day's best-ranked rows that have no embedding, `batch` rows per round trip.

    Same limit as enrich_day: the top EMBED_TOP_PER_DAY stories of every day (50 by
    default, 0 for all). Rows beyond it are left alone, so this terminates.
    """
    if not embeddings.is_configured():
        print("❌ VOYAGE_API_KEY is not set.")
        return 0
    top_n = embeddings.top_per_day()
    total = 0
    while True:
        rows = db.find_rows_missing_embedding(limit=batch, top_n=top_n)
        if not rows:
            break
        vectors = embeddings.embed_documents([embeddings.document_text(r) for r in rows])
        total += db.update_embeddings([
            (r["id"], embeddings.to_vector_literal(v)) for r, v in zip(rows, vectors)
        ])
        print(f"  ...{total} embedded")
    print(f"✅ Embedded {total} rows.")
    return total


if __name__ == "__main__":
    import sys

    args = sys.argv[1:]

    if args and args[0] == "backfill-missing":
        MissingDaysBackfiller(DatabaseConnection(table_name="news")).run()
    elif args and args[0] == "repair-descriptions":
        DescriptionRepairer(DatabaseConnection(table_name="news")).run()
    elif args and args[0] == "repair-images":
        ImageRepairer(DatabaseConnection(table_name="news")).run()
    elif args and args[0] == "prune-irrelevant":
        prune_irrelevant(DatabaseConnection(table_name="news"))
    elif args and args[0] == "trim-days":
        trim_days(DatabaseConnection(table_name="news"))
    elif args and args[0] == "rescore":
        rescore(DatabaseConnection(table_name="news"), *args[1:3])
    elif args and args[0] == "backfill-embeddings":
        backfill_embeddings(DatabaseConnection(table_name="news"))
    elif args and args[0] == "enrich":
        # Re-run embeddings + digest + NOTIFY for a date or range without scraping.
        utils = Utility(table_name="news")
        start, end = utils.get_date_range(*(args[1:3] or [None]))
        if not start:
            sys.exit(2)
        for n in range((end - start).days + 1):
            enrich_day(utils.db, start + dt.timedelta(days=n))
    else:
        start_date_arg = args[0] if len(args) > 0 else None
        end_date_arg = args[1] if len(args) > 1 else None
        storage = NewsStorage()
        storage.run(start_date_arg, end_date_arg)
        if storage.degraded_days:
            print(f"❌ GDELT failed for {len(storage.degraded_days)} day(s): {storage.degraded_days}")
            sys.exit(1)
