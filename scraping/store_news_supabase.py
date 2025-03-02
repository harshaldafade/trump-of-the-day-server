import os
from supabase import create_client, Client
from dotenv import load_dotenv
from news_scraper import fetch_news_by_date
import datetime
import time

# Load environment variables
load_dotenv()

# Supabase credentials
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("⚠️ Supabase credentials are missing. Check your .env file.")

# Connect to Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Table Name
TABLE_NAME = "news"

def save_news_by_date(target_date):
    """Fetches and stores news for a specific date in Supabase."""
    news = fetch_news_by_date(target_date)
    if not news:
        print(f"⚠️ No news fetched for {target_date}.")
        return

    for article in news:
        data = {
            "created_at": datetime.datetime.utcnow().isoformat(),  # UTC timestamp
            "date": article["date"],  # The actual news date
            "title": article["title"],
            "description": article["description"],
            "link": article["link"],
            "news_source": article["news_source"],
            "image_url": article["image_url"],
        }

        try:
            response = supabase.table(TABLE_NAME).insert(data).execute()
            print(f"✅ Inserted news for {target_date}: {article['title']}")
        except Exception as e:
            print(f"❌ Error inserting data for {target_date}: {e}")

if __name__ == "__main__":
    start_date = datetime.date(2025, 1, 20)  # Start scraping from January 20th, 2025
    end_date = datetime.date.today()

    for single_date in (start_date + datetime.timedelta(days=n) for n in range((end_date - start_date).days + 1)):
        print(f"📅 Fetching and storing news for {single_date}")
        save_news_by_date(single_date)
        time.sleep(2)  # Prevent Google from blocking requests
