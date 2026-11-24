import os
import psycopg2
from psycopg2 import sql
from psycopg2.extras import Json, RealDictCursor, execute_values
from dotenv import load_dotenv
import datetime
import time


def today_utc():
    """Today's date in UTC: the day boundary the site and API use, whatever the machine's timezone."""
    return datetime.datetime.now(datetime.timezone.utc).date()


class Utility:
    """Utility class for Neon database operations common to both news storage and deletion."""
    
    def __init__(self, table_name):
        # Initialize the database connection
        self.db = DatabaseConnection(table_name)
        self.table_name = table_name
    
    def get_date_range(self, start_date_str=None, end_date_str=None):
        """
        Gets and validates date range from provided strings or defaults to today.
        
        Args:
            start_date_str: String in format YYYY-MM-DD, 'today', 't', or None (defaults to today)
            end_date_str: String in format YYYY-MM-DD or None (defaults to same as start_date)
            
        Returns:
            Tuple of (start_date, end_date) as datetime.date objects or (None, None) if invalid
        """
        try:
            # If no start date provided or 'today'/'t' specified, use today's date
            if not start_date_str or start_date_str.lower() in ['today', 't']:
                start_date = today_utc()
            elif start_date_str.lower() in ['yesterday', 'y']:
                start_date = today_utc() - datetime.timedelta(days=1)
            else:
                # Parse the provided start date
                start_date = datetime.datetime.strptime(start_date_str, "%Y-%m-%d").date()
                
            # If no end date provided, use the same as start date
            if not end_date_str:
                end_date = start_date
            elif end_date_str.lower() in ['today', 't']:
                end_date = today_utc()
            else:
                # Parse the provided end date
                end_date = datetime.datetime.strptime(end_date_str, "%Y-%m-%d").date()
            
            # Validate date range
            if start_date > end_date:
                print("Error: Start date cannot be after end date.")
                return None, None
            
            return start_date, end_date
        
        except ValueError as e:
            print(f"Error: Invalid date format. Please use YYYY-MM-DD format. Details: {e}")
            return None, None
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            return None, None
    
    def format_date(self, date):
        """Formats a date object to match the database format."""
        return date.strftime("%Y-%m-%d")
    
    def process_date_range(self, start_date, end_date, operation_func, delay=1):
        """
        Processes a function for each date in the given range.
        
        Args:
            start_date: The starting date
            end_date: The ending date
            operation_func: Function to call for each date
            delay: Time to sleep between operations
        
        Returns:
            Total count of processed items
        """
        if not start_date or not end_date:
            return 0
            
        print(f"📅 Processing from {start_date} to {end_date}")
        
        total_count = 0
        # Loop through each date in the range
        for single_date in (start_date + datetime.timedelta(days=n) for n in range((end_date - start_date).days + 1)):
            print(f"📅 Processing operation for {single_date}")
            count = operation_func(single_date)
            total_count += count
            time.sleep(delay)  # Delay between operations
        
        print(f"✅ Completed processing for date range: {start_date} to {end_date}")
        return total_count

class DatabaseConnection:
    """Functions for interacting with the Postgres (Neon) database"""
    def __init__(self, table_name):
        # Load environment variables
        load_dotenv()

        self.database_url = os.getenv("DATABASE_URL")

        if not self.database_url:
            raise ValueError("⚠️ DATABASE_URL is missing. Check your .env file.")

        # Table Name
        self.table_name = table_name

    def _connect(self):
        return psycopg2.connect(self.database_url)

    def insert_record(self, data):
        """
        Insert a record into the database table.

        Args:
            data (dict): The data to insert

        Returns:
            dict: The response from the database

        Raises:
            Exception: If an error occurs during insertion
        """
        try:
            columns = list(data.keys())
            query = sql.SQL("INSERT INTO {table} ({fields}) VALUES ({placeholders})").format(
                table=sql.Identifier(self.table_name),
                fields=sql.SQL(", ").join(map(sql.Identifier, columns)),
                placeholders=sql.SQL(", ").join(sql.Placeholder() * len(columns)),
            )
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, [data[c] for c in columns])
            return {"inserted": True}
        except Exception as e:
            raise Exception(f"Error inserting data: {e}")

    def insert_records(self, data_list):
        """
        Insert many records in a single connection/transaction instead of one
        connection per row (matters once volumes get into the hundreds/thousands,
        both for speed and for not hammering Neon with connection churn).

        Rows whose `link` already exists are skipped (`ON CONFLICT (md5(link)) DO
        NOTHING`, backed by the news_link_md5_key unique index from migration
        002; a hash because some links are too long to index directly), so
        re-running a day -- e.g. the daily job re-scraping yesterday to pick up
        stories published after the previous run -- only adds what's new.

        Args:
            data_list (list[dict]): Records to insert; all dicts must share the same keys.

        Returns:
            int: Number of rows actually inserted (duplicates excluded)

        Raises:
            Exception: If an error occurs during insertion
        """
        if not data_list:
            return 0

        try:
            columns = list(data_list[0].keys())
            values = [[row[c] for c in columns] for row in data_list]
            with self._connect() as conn:
                with conn.cursor() as cur:
                    query = sql.SQL(
                        "INSERT INTO {table} ({fields}) VALUES %s ON CONFLICT (md5(link)) DO NOTHING RETURNING id"
                    ).format(
                        table=sql.Identifier(self.table_name),
                        fields=sql.SQL(", ").join(map(sql.Identifier, columns)),
                    ).as_string(cur)
                    inserted = execute_values(cur, query, values, fetch=True)
            return len(inserted)
        except Exception as e:
            raise Exception(f"Error bulk inserting data: {e}")

    def fetch_ranked_by_date(self, date, limit=None):
        """
        Rows for one date, best relevance first -- the input to the daily digest.

        Returns:
            list[dict]: id, title, description, news_source, link
        """
        if isinstance(date, datetime.date):
            date = date.strftime("%Y-%m-%d")
        query = sql.SQL("""
            SELECT id, title, description, news_source, link FROM {table}
            WHERE date = %s
            ORDER BY relevance_score DESC NULLS LAST, id
            LIMIT %s
        """).format(table=sql.Identifier(self.table_name))
        with self._connect() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, [date, limit])
                return [dict(row) for row in cur.fetchall()]

    def find_rows_missing_embedding(self, date=None, limit=5000):
        """
        Rows with no embedding yet, optionally limited to one date.

        Returns:
            list[dict]: id, title, description
        """
        if isinstance(date, datetime.date):
            date = date.strftime("%Y-%m-%d")
        query = sql.SQL("""
            SELECT id, title, description FROM {table}
            WHERE embedding IS NULL AND (%s::date IS NULL OR date = %s::date)
            ORDER BY id
            LIMIT %s
        """).format(table=sql.Identifier(self.table_name))
        with self._connect() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, [date, date, limit])
                return [dict(row) for row in cur.fetchall()]

    def update_embeddings(self, updates):
        """
        Bulk-set embeddings.

        Args:
            updates (list[tuple]): (id, vector_literal) where vector_literal is
                pgvector text like '[0.1,0.2,...]' (lib.embeddings.to_vector_literal)

        Returns:
            int: Number of rows updated
        """
        if not updates:
            return 0
        with self._connect() as conn:
            with conn.cursor() as cur:
                execute_values(
                    cur,
                    sql.SQL(
                        "UPDATE {table} SET embedding = data.embedding::vector "
                        "FROM (VALUES %s) AS data(id, embedding) "
                        "WHERE {table}.id = data.id"
                    ).format(table=sql.Identifier(self.table_name)).as_string(cur),
                    updates,
                )
        return len(updates)

    def fetch_for_scoring(self, start_date=None, end_date=None):
        """
        Columns lib.relevance.score_article reads, for re-scoring existing rows.

        Returns:
            list[dict]: id, title, description, link, news_source, image_url
        """
        query = sql.SQL("""
            SELECT id, title, description, link, news_source, image_url FROM {table}
            WHERE (%s::date IS NULL OR date >= %s::date) AND (%s::date IS NULL OR date <= %s::date)
        """).format(table=sql.Identifier(self.table_name))
        with self._connect() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, [start_date, start_date, end_date, end_date])
                return [dict(row) for row in cur.fetchall()]

    def update_relevance(self, updates):
        """
        Bulk-set relevance_score.

        Args:
            updates (list[tuple]): (id, score)

        Returns:
            int: Number of rows updated
        """
        if not updates:
            return 0
        with self._connect() as conn:
            with conn.cursor() as cur:
                execute_values(
                    cur,
                    sql.SQL(
                        "UPDATE {table} SET relevance_score = data.score "
                        "FROM (VALUES %s) AS data(id, score) "
                        "WHERE {table}.id = data.id"
                    ).format(table=sql.Identifier(self.table_name)).as_string(cur),
                    updates,
                )
        return len(updates)

    def upsert_digest(self, date, digest):
        """
        Insert or replace the daily_digest row for `date`.

        Args:
            digest (dict): summary, paragraphs, top_story_ids, model (lib.digest.generate_digest
                output). paragraphs (sentences with the story ids they cite) may be None.
        """
        if isinstance(date, datetime.date):
            date = date.strftime("%Y-%m-%d")
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO daily_digest (date, summary, paragraphs, top_story_ids, model)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (date) DO UPDATE SET
                        summary = EXCLUDED.summary,
                        paragraphs = EXCLUDED.paragraphs,
                        top_story_ids = EXCLUDED.top_story_ids,
                        model = EXCLUDED.model,
                        created_at = now()
                    """,
                    [
                        date,
                        digest["summary"],
                        Json(digest["paragraphs"]) if digest.get("paragraphs") else None,
                        digest["top_story_ids"],
                        digest["model"],
                    ],
                )

    def notify_news_updated(self, date):
        """
        Tell running API instances that `date` changed (Postgres NOTIFY on
        channel news_updated). Each instance drops its cached copy of that date
        and pushes a WebSocket message to connected browsers.
        """
        if isinstance(date, datetime.date):
            date = date.strftime("%Y-%m-%d")
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT pg_notify('news_updated', %s)", [date])

    def update_record(self, id, data):
        """
        Update a record in the database table.

        Args:
            id: The record ID to update
            data (dict): The data to update

        Returns:
            dict: The response from the database

        Raises:
            Exception: If an error occurs during update
        """
        try:
            columns = list(data.keys())
            set_clause = sql.SQL(", ").join(
                sql.SQL("{} = {}").format(sql.Identifier(c), sql.Placeholder()) for c in columns
            )
            query = sql.SQL("UPDATE {table} SET {set_clause} WHERE id = %s").format(
                table=sql.Identifier(self.table_name),
                set_clause=set_clause,
            )
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, [data[c] for c in columns] + [id])
                    rowcount = cur.rowcount
            return rowcount
        except Exception as e:
            raise Exception(f"Error updating data: {e}")

    def delete_record(self, id):
        """
        Delete a record from the database table.

        Args:
            id: The record ID to delete

        Returns:
            dict: The response from the database

        Raises:
            Exception: If an error occurs during deletion
        """
        try:
            query = sql.SQL("DELETE FROM {table} WHERE id = %s").format(table=sql.Identifier(self.table_name))
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, [id])
                    rowcount = cur.rowcount
            return rowcount
        except Exception as e:
            raise Exception(f"Error deleting data: {e}")

    def delete_by_date(self, date):
        """
        Delete records for a specific date.

        Args:
            date: The date to delete records for (as a string or date object)

        Returns:
            int: Number of records deleted

        Raises:
            Exception: If an error occurs during deletion
        """
        try:
            # Ensure date is in string format if a date object is passed
            if isinstance(date, datetime.date):
                date = date.strftime("%Y-%m-%d")

            query = sql.SQL("DELETE FROM {table} WHERE date = %s").format(table=sql.Identifier(self.table_name))
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, [date])
                    rowcount = cur.rowcount
            return rowcount
        except Exception as e:
            raise Exception(f"Error deleting data for date {date}: {e}")

    def fetch_records(self, limit=100, offset=0):
        """
        Fetch records from the database table with pagination.

        Args:
            limit (int): Maximum number of records to fetch
            offset (int): Number of records to skip

        Returns:
            list: The fetched records

        Raises:
            Exception: If an error occurs during fetching
        """
        try:
            query = sql.SQL("SELECT * FROM {table} LIMIT %s OFFSET %s").format(table=sql.Identifier(self.table_name))
            with self._connect() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(query, [limit, offset])
                    return [dict(row) for row in cur.fetchall()]
        except Exception as e:
            raise Exception(f"Error fetching data: {e}")

    def fetch_by_date(self, date):
        """
        Fetch records for a specific date.

        Args:
            date: The date to fetch records for (as a string or date object)

        Returns:
            list: The fetched records

        Raises:
            Exception: If an error occurs during fetching
        """
        try:
            # Ensure date is in string format if a date object is passed
            if isinstance(date, datetime.date):
                date = date.strftime("%Y-%m-%d")

            query = sql.SQL("SELECT * FROM {table} WHERE date = %s").format(table=sql.Identifier(self.table_name))
            with self._connect() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(query, [date])
                    return [dict(row) for row in cur.fetchall()]
        except Exception as e:
            raise Exception(f"Error fetching data for date {date}: {e}")

    def find_missing_dates(self):
        """
        Find every date with zero rows between the table's earliest date and yesterday.

        Returns:
            list[datetime.date]: Missing dates, ascending

        Raises:
            Exception: If an error occurs during the query
        """
        try:
            query = sql.SQL("""
                SELECT gs::date
                FROM generate_series(
                    (SELECT min(date) FROM {table}),
                    CURRENT_DATE - INTERVAL '1 day',
                    interval '1 day'
                ) gs
                LEFT JOIN {table} ON {table}.date = gs::date
                WHERE {table}.date IS NULL
                ORDER BY 1
            """).format(table=sql.Identifier(self.table_name))
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(query)
                    return [row[0] for row in cur.fetchall()]
        except Exception as e:
            raise Exception(f"Error finding missing dates: {e}")

    def find_rows_missing_description(self):
        """
        Find rows with no description whose link is at least plausibly fetchable
        (i.e. not a Google News redirect link, which can't be scraped server-side).

        Returns:
            list[tuple]: (id, link, image_url) for each candidate row

        Raises:
            Exception: If an error occurs during the query
        """
        try:
            query = sql.SQL("""
                SELECT id, link, image_url FROM {table}
                WHERE (description IS NULL OR description = '')
                  AND link ~ '^https?://'
                  AND link NOT LIKE '%%google.com%%'
                ORDER BY id
            """).format(table=sql.Identifier(self.table_name))
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(query)
                    return cur.fetchall()
        except Exception as e:
            raise Exception(f"Error finding rows missing a description: {e}")

    def update_descriptions(self, updates):
        """
        Bulk-update description (and image_url) for many rows in one connection/transaction.

        Args:
            updates (list[tuple]): (id, description, image_url) tuples

        Returns:
            int: Number of rows updated

        Raises:
            Exception: If an error occurs during the update
        """
        if not updates:
            return 0

        try:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    execute_values(
                        cur,
                        sql.SQL(
                            "UPDATE {table} SET description = data.description, image_url = data.image_url "
                            "FROM (VALUES %s) AS data(id, description, image_url) "
                            "WHERE {table}.id = data.id"
                        ).format(table=sql.Identifier(self.table_name)).as_string(cur),
                        updates,
                    )
            return len(updates)
        except Exception as e:
            raise Exception(f"Error bulk updating descriptions: {e}")