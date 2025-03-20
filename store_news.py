from datetime import datetime, UTC
from utils import Utility
from news_scraper import fetch_news_by_date

class NewsStorage:
    """Class for fetching and storing news in Supabase."""
    
    def __init__(self):
        self.utils = Utility(table_name="news")
    
    def save_news_by_date(self, target_date):
        """
        Fetches and stores news for a specific date in Supabase.
        
        Args:
            target_date: The date to fetch news for
            
        Returns:
            Number of articles saved
        """
        news = fetch_news_by_date(target_date)
        if not news:
            print(f"⚠️ No news fetched for {target_date}.")
            return 0

        articles_saved = 0
        for article in news:
            data = {
                "created_at": datetime.now(UTC).isoformat(),  # UTC timestamp
                "date": article["date"],  # The actual news date
                "title": article["title"],
                "description": article["description"],
                "link": article["link"],
                "news_source": article["news_source"],
                "image_url": article["image_url"],
            }

            try:
                response = self.utils.supabase.table(self.utils.table_name).insert(data).execute()
                # print(f"✅ Inserted news for {target_date}: {article['title']}")
                articles_saved += 1
            except Exception as e:
                print(f"❌ Error inserting data for {target_date}: {e}")
        
        return articles_saved

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