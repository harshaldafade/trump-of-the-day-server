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
            "created_at": datetime.datetime.now(datetime.UTC).isoformat(),  # UTC timestamp
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
    import argparse
    
    # Set up argument parser
    parser = argparse.ArgumentParser(description="Fetch and store news articles by date range")
    parser.add_argument("--start", type=str, help="Start date in YYYY-MM-DD format")
    parser.add_argument("--end", type=str, help="End date in YYYY-MM-DD format")
    
    args = parser.parse_args()
    
    try:
        # Default to today's date if no arguments provided
        if args.start is None and args.end is None:
            today = datetime.date.today()
            start_date = today
            end_date = today
            print(f"🔍 No dates provided. Processing news for today: {today}")
        else:
            # If only one date is provided, use it for both start and end
            if args.start and not args.end:
                args.end = args.start
            elif args.end and not args.start:
                args.start = args.end
                
            # Convert string input to date objects
            start_date = datetime.datetime.strptime(args.start, "%Y-%m-%d").date()
            end_date = datetime.datetime.strptime(args.end, "%Y-%m-%d").date()
            
            # Validate date range
            if start_date > end_date:
                print("Error: Start date cannot be after end date.")
                exit(1)
                
            print(f"🔍 Processing news from {start_date} to {end_date}")
        
        # Loop through each date in the range
        for single_date in (start_date + datetime.timedelta(days=n) for n in range((end_date - start_date).days + 1)):
            print(f"📅 Fetching and storing news for {single_date}")
            save_news_by_date(single_date)
            time.sleep(2)  # Prevent Google from blocking requests
        
        print(f"✅ Completed processing news for date range: {start_date} to {end_date}")
    
    except ValueError as e:
        print(f"Error: Invalid date format. Please use YYYY-MM-DD format. Details: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")