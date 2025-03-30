from datetime import datetime, timedelta, UTC
from lib.utils import Utility, DatabaseConnection  # Assuming you have these defined elsewhere
from news_scraper2 import fetch_news_by_date

# Load environment variables

class NewsStorage:
    """Class for fetching and storing news in Supabase."""
    
    def __init__(self):
        self.utils = Utility(table_name="news_articles")
        self.db = self.utils.db  # Use the DatabaseConnection instance from Utility
    
    def push_to_supabase(self, articles):
        """
        Inserts articles into the Supabase table.
        Automatically avoids duplicates by URL hash.
        """
        saved_count = 0
        for article in articles:
            try:
                # Extract url_hash from the article dictionary
                url_hash = article.get("url_hash", None)

                if not url_hash:
                    print(f"❌ No url_hash found for {article['title']}. Skipping.")
                    continue

                # Check if the article exists using the url_hash
                existing = self.db.select_record("url_hash", url_hash)

                if existing:
                    print(f"⚠️ Skipped (likely duplicate): {article['title']}")
                    continue

                # Insert the article
                self.db.insert_record(article)
                print(f"✅ Inserted: {article['title']}")
                saved_count += 1

            except Exception as e:
                print(f"❌ Error inserting data for {article['title']}: {e}")
    
        return saved_count


    def save_news_by_date(self, target_date):
        """
        Fetches and stores news for a specific date in Supabase.
        """
        print(f"📅 Running scraper for {target_date}")
        articles = fetch_news_by_date(target_date)
        
        if not articles:
            print(f"⚠️ No articles returned for {target_date}.")
            return 0
        
        saved_count = self.push_to_supabase(articles)
        print(f"📊 {saved_count} articles saved for {target_date}")
        return saved_count

    def run(self, start_date_str=None, end_date_str=None):
        """
        Main method to run the news storage process.
        
        Args:
            start_date_str: Optional start date (YYYY-MM-DD or 'today'/'t')
            end_date_str: Optional end date (YYYY-MM-DD)
        """
        try:
            # Use the updated date range method that accepts parameters
            start_date, end_date = self.utils.get_date_range(start_date_str, end_date_str)
            if not start_date or not end_date:
                return
                
            print(f"🔍 Processing news from {start_date} to {end_date}")
            
            # Use 2 second delay to prevent Google from blocking requests
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


if __name__ == "__main__":
    import sys
    
    # Parse command line arguments if provided
    start_date_arg = sys.argv[1] if len(sys.argv) > 1 else None
    end_date_arg = sys.argv[2] if len(sys.argv) > 2 else None
    
    storage = NewsStorage()
    storage.run(start_date_arg, end_date_arg)
