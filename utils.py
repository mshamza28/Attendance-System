"""Utility functions for the attendance system."""

from datetime import datetime, timedelta
import pandas as pd


def format_time(time_str):
    """Format time string for display.
    
    Args:
        time_str: Time string to format
        
    Returns:
        str: Formatted time string or "-" if None
    """
    if not time_str:
        return "-"
    return time_str


def date_range(start_date, end_date):
    """Create a list of dates between start_date and end_date.
    
    Args:
        start_date: Start date
        end_date: End date
        
    Returns:
        list: List of date strings in YYYY-MM-DD format
    """
    delta = end_date - start_date
    days = [start_date + timedelta(days=i) for i in range(delta.days + 1)]
    return [day.strftime('%Y-%m-%d') for day in days]


def format_dataframe_for_display(df):
    """Format a DataFrame for display in Streamlit.
    
    Args:
        df: pandas DataFrame to format
        
    Returns:
        pandas.DataFrame.style: Styled DataFrame
    """
    if df.empty:
        return df
        
    # Create a copy to avoid modifying the original
    display_df = df.copy()
    
    # Format times
    if 'check_in' in display_df.columns:
        display_df['check_in'] = display_df['check_in'].apply(format_time)
    if 'check_out' in display_df.columns:
        display_df['check_out'] = display_df['check_out'].apply(format_time)
        
    # Format hours_worked to 2 decimal places
    if 'hours_worked' in display_df.columns:
        display_df['hours_worked'] = display_df['hours_worked'].apply(
            lambda x: f"{x:.2f}" if pd.notnull(x) else "-"
        )
    
    # Apply status-based color formatting
    def highlight_status(row):
        if 'status' in row and row.status == 'present':
            return ['background-color: #d4edda'] * len(row)
        elif 'status' in row and row.status == 'absent':
            return ['background-color: #f8d7da'] * len(row)
        elif 'status' in row and row.status == 'late':
            return ['background-color: #fff3cd'] * len(row)
        return [''] * len(row)
    
    return display_df.style.apply(highlight_status, axis=1)


def get_date_defaults():
    """Get default dates for UI elements.
    
    Returns:
        tuple: (today, week_ago, first_day_of_month)
    """
    today = datetime.now().date()
    week_ago = today - timedelta(days=7)
    first_day_of_month = today.replace(day=1)
    
    return today, week_ago, first_day_of_month