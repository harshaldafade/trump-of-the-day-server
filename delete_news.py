from datetime import datetime
from lib.utils import Utility

class NewsDeletion:
    """Class for deleting news from Supabase."""
    
    def __init__(self):
        self.utils = Utility(table_name="news")
    
    def delete_news_by_date(self, target_date):
        """
        Deletes news articles for a specific date from Supabase.
        
        Args:
            target_date: The date to delete news for
            
        Returns:
            Number of articles deleted
        """
        # Format the date to match the date format in the database
        formatted_date = self.utils.format_date(target_date)
        
        try:
            # Query to find and delete news with matching date
            response = self.utils.supabase.table(self.utils.table_name).delete().eq("date", formatted_date).execute()
            
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
    
    def run(self, start_date_str=None, end_date_str=None, confirm=False):
        """
        Main method to run the news deletion process.
        
        Args:
            start_date_str: Optional start date (YYYY-MM-DD or 'today'/'t')
            end_date_str: Optional end date (YYYY-MM-DD)
            confirm: Skip confirmation prompt if True
        
        Returns:
            Number of articles deleted or 0 if operation was cancelled or failed
        """
        try:
            # Use the updated date range method that accepts parameters
            start_date, end_date = self.utils.get_date_range(start_date_str, end_date_str)
            if not start_date or not end_date:
                return 0
            
            # Ask for confirmation before deleting unless explicitly confirmed
            if not confirm:
                print(f"⚠️ You are about to delete all news articles from {start_date} to {end_date}")
                confirmation = input("Are you sure you want to proceed? (yes/no): ").lower()
                
                if confirmation != 'yes':
                    print("Operation cancelled.")
                    return 0
            
            print(f"🗑️ Deleting news from {start_date} to {end_date}")
            
            total_deleted = self.utils.process_date_range(
                start_date, 
                end_date, 
                self.delete_news_by_date
            )
            
            print(f"📊 Total articles deleted: {total_deleted}")
            return total_deleted
            
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            return 0

if __name__ == "__main__":
    import sys
    
    # Parse command line arguments if provided
    args = sys.argv
    start_date_arg = args[1] if len(args) > 1 else None
    end_date_arg = args[2] if len(args) > 2 else None
    force_confirm = True if len(args) > 3 and args[3].lower() in ['--force', '-f', 'yes', 'y'] else False
    
    deletion = NewsDeletion()
    deletion.run(start_date_arg, end_date_arg, force_confirm)