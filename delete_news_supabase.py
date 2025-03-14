import os
from supabase import create_client, Client
from dotenv import load_dotenv
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

def delete_news_by_date(target_date):
    """Deletes news articles for a specific date from Supabase."""
    # Format the date to match the date format in the database
    formatted_date = target_date.strftime("%Y-%m-%d")
    
    try:
        # Query to find and delete news with matching date
        response = supabase.table(TABLE_NAME).delete().eq("date", formatted_date).execute()
        
        # Check how many records were deleted
        deleted_count = len(response.data)
        if deleted_count > 0:
            print(f"✅ Deleted {deleted_count} news articles for {formatted_date}")
        else:
            print(f"ℹ️ No news articles found for {formatted_date}")
            
        return deleted_count
    except Exception as e:
        print(f"❌ Error deleting data for {formatted_date}: {e}")
        return 0

if __name__ == "__main__":
   import argparse
   
   # Set up argument parser
   parser = argparse.ArgumentParser(description="Delete news articles by date range")
   parser.add_argument("--start", type=str, help="Start date in YYYY-MM-DD format")
   parser.add_argument("--end", type=str, help="End date in YYYY-MM-DD format")
   parser.add_argument("--force", action="store_true", help="Skip confirmation prompt")
   
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
               
           print(f"🔍 Processing date range: {start_date} to {end_date}")
       
       # Ask for confirmation before deleting (unless --force flag is used)
       if not args.force:
           print(f"⚠️ You are about to delete all news articles from {start_date} to {end_date}")
           confirmation = input("Are you sure you want to proceed? (yes/no): ").lower()
           
           if confirmation != 'yes':
               print("Operation cancelled.")
               exit(0)

       print(f"🗑️ Deleting news from {start_date} to {end_date}")

       total_deleted = 0
       # Loop through each date in the range
       for single_date in (start_date + datetime.timedelta(days=n) for n in range((end_date - start_date).days + 1)):
           print(f"📅 Processing delete operation for {single_date}")
           deleted = delete_news_by_date(single_date)
           total_deleted += deleted
           time.sleep(1)  # Small delay between operations

       print(f"✅ Completed deleting news for date range: {start_date} to {end_date}")
       print(f"📊 Total articles deleted: {total_deleted}")
   
   except ValueError as e:
       print(f"Error: Invalid date format. Please use YYYY-MM-DD format. Details: {e}")
   except Exception as e:
       print(f"An unexpected error occurred: {e}")