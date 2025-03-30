import os
from supabase import create_client, Client
from dotenv import load_dotenv
import datetime
import time

class Utility:
    """Utility class for Supabase operations common to both news storage and deletion."""
    
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
                start_date = datetime.date.today()
            else:
                # Parse the provided start date
                start_date = datetime.datetime.strptime(start_date_str, "%Y-%m-%d").date()
                
            # If no end date provided, use the same as start date
            if not end_date_str:
                end_date = start_date
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
    """Functions for interacting with Supabase Database"""
    def __init__(self, table_name):
        # Load environment variables
        load_dotenv()
        
        # Supabase credentials
        self.supabase_url = os.getenv("SUPABASE_URL")
        self.supabase_key = os.getenv("SUPABASE_KEY")
        
        if not self.supabase_url or not self.supabase_key:
            raise ValueError("⚠️ Supabase credentials are missing. Check your .env file.")
        
        # Connect to Supabase
        self.supabase: Client = create_client(self.supabase_url, self.supabase_key)
        
        # Table Name
        self.table_name = table_name
    
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
            response = self.supabase.table(self.table_name).insert(data).execute()
            return response
        except Exception as e:
            raise Exception(f"Error inserting data: {e}")
    
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
            response = self.supabase.table(self.table_name).update(data).eq("id", id).execute()
            return response
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
            response = self.supabase.table(self.table_name).delete().eq("id", id).execute()
            return response
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
            
            response = self.supabase.table(self.table_name).delete().eq("date", date).execute()
            return len(response.data) if hasattr(response, 'data') else 0
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
            response = self.supabase.table(self.table_name).select("*").limit(limit).offset(offset).execute()
            return response.data
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
            
            response = self.supabase.table(self.table_name).select("*").eq("date", date).execute()
            return response.data
        except Exception as e:
            raise Exception(f"Error fetching data for date {date}: {e}")
        
    def select_record(self, column, value):
        """Check for duplicates by column and value."""
        try:
            response = self.supabase.table(self.table_name).select("*").eq(column, value).execute()
            return response.data if response.data else None
        except Exception as e:
            print(f"❌ Error selecting record: {e}")
            return None