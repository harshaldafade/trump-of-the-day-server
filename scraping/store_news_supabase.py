import os
from supabase import create_client, Client
from dotenv import load_dotenv
from news_scraper import fetch_news
import datetime

# Load environment variables from .env file
load_dotenv()

# Get Supabase credentials from environment variables
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Ensure credentials exist
if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Supabase credentials are missing. Check your .env file.")

# Connect to Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def save_news():
    """Fetches and stores news in Supabase."""
    news = fetch_news()
    if not news:
        print("No news fetched.")
        return

    for article in news:
        data = {
            "created_at": datetime.datetime.utcnow().isoformat(),
            "date": article["date"],
            "link": article["link"],
        }
        response = supabase.table("news").insert(data).execute()
        print(response)

if __name__ == "__main__":
    save_news()
