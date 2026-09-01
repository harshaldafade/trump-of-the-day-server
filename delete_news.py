from lib.utils import Utility, DatabaseConnection

class NewsDeletion:
    """Class for deleting news from the Neon database."""
    
    def __init__(self):
        self.utils = Utility(table_name="news")
        self.db = self.utils.db  # Use the DatabaseConnection instance from Utility
    
    def delete_news_by_date(self, target_date):
        """
        Deletes news articles for a specific date from the Neon database.
        
        Args:
            target_date: The date to delete news for
            
        Returns:
            Number of articles deleted
        """
        try:
            # Use the database connection delete_by_date method
            deleted_count = self.db.delete_by_date(target_date)
            
            if deleted_count > 0:
                print(f"✅ Deleted {deleted_count} news articles for {target_date}")
            else:
                print(f"ℹ️ No news articles found for {target_date}")
                
            return deleted_count
        except Exception as e:
            print(f"❌ Error deleting data for {target_date}: {e}")
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

    # The force flag can appear in any position (e.g. "2025-09-10 --force" with no
    # end date), so it's pulled out separately rather than assumed to be argv[3].
    FORCE_FLAGS = {"--force", "-f", "yes", "y"}
    args = sys.argv[1:]
    force_confirm = any(a.lower() in FORCE_FLAGS for a in args)
    date_args = [a for a in args if a.lower() not in FORCE_FLAGS]

    start_date_arg = date_args[0] if len(date_args) > 0 else None
    end_date_arg = date_args[1] if len(date_args) > 1 else None

    deletion = NewsDeletion()
    deletion.run(start_date_arg, end_date_arg, force_confirm)