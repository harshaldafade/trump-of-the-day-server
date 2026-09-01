from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor

from lib.utils import Utility, DatabaseConnection
from news_scraper import fetch_news_by_date, fetch_meta, build_session, is_google_link


def _build_records(articles):
    """Turn scraped article dicts into rows ready for DatabaseConnection.insert_records."""
    created_at = datetime.now(timezone.utc).isoformat()
    return [{
        "created_at": created_at,
        "date": article["date"],
        "title": article["title"],
        "description": article["description"],
        "link": article["link"],
        "news_source": article["news_source"],
        "image_url": article["image_url"],
    } for article in articles]


class NewsStorage:
    """Fetches and stores news for a given date or date range."""

    def __init__(self):
        self.utils = Utility(table_name="news")
        self.db = self.utils.db

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
            return 0

        try:
            # Insert the whole day's articles in one connection/transaction instead
            # of one connection per row.
            return self.db.insert_records(_build_records(news))
        except Exception as e:
            print(f"❌ Error inserting data for {target_date}: {e}")
            return 0

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
                records.extend(_build_records(articles))
            except Exception as e:
                print(f"  ❌ scrape failed for {day}: {e}")

        if not records:
            print("⚠️ Nothing scraped, nothing to insert.")
            return 0

        print(f"📥 Inserting {len(records)} articles across {len(missing_days)} day(s) in one request...")
        count = self.db.insert_records(records)
        print(f"✅ Inserted {count} rows.")
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


if __name__ == "__main__":
    import sys

    args = sys.argv[1:]

    if args and args[0] == "backfill-missing":
        MissingDaysBackfiller(DatabaseConnection(table_name="news")).run()
    elif args and args[0] == "repair-descriptions":
        DescriptionRepairer(DatabaseConnection(table_name="news")).run()
    else:
        start_date_arg = args[0] if len(args) > 0 else None
        end_date_arg = args[1] if len(args) > 1 else None
        NewsStorage().run(start_date_arg, end_date_arg)
