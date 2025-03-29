import os
import datetime
import time
from supabase import create_client
from dotenv import load_dotenv
from news_scraper2 import fetch_news_by_date

# Load .env variables
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
TABLE_NAME = "news_articls"

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("❌ Missing Supabase credentials in .env")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def push_to_supabase(articles):
    for article in articles:
        try:
            response = supabase.table(TABLE_NAME).insert(article).execute()
            if response.data:
                print(f"✅ Inserted: {article['title']}")
        except Exception as e:
            print(f"⚠️ Skipped (likely duplicate): {article['title']} — {e}")

def run_scraper_for_date(target_date):
    print(f"📅 Running scraper for {target_date}")
    articles = fetch_news_by_date(target_date)
    if not articles:
        print("⚠️ No articles returned.")
        return
    push_to_supabase(articles)

if __name__ == "__main__":
    today = datetime.date.today()
    run_scraper_for_date(today)
    time.sleep(2)
