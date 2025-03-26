"""Main application file for the Attendance Management System."""

import streamlit as st
import os
import time
import sqlite3
import gc
from database import AttendanceSystemDB
from pages.dashboard import render_dashboard
from pages.mark_attendance import render_mark_attendance
from pages.view_attendance import render_view_attendance
from pages.reports import render_reports
from pages.user_management import render_user_management
from pages.settings import render_settings

# Initialize Streamlit app - THIS MUST COME FIRST
st.set_page_config(
    page_title="Attendance Management System",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded"
)


def hide_default_navigation():
    """Hide the default file navigation in the sidebar without affecting custom navigation."""
    st.markdown("""
    <style>
    /* Hide only the auto-generated file navigation items */
    section[data-testid="stSidebar"] > div.css-163ttbj > div:nth-child(1) {
        display: none !important;
    }
    /* Keep the custom navigation visible */
    section[data-testid="stSidebar"] > div.css-163ttbj > div:nth-child(2) {
        display: block !important;
    }
    </style>
    """, unsafe_allow_html=True)

# Call this function AFTER set_page_config
hide_default_navigation()

# Initialize database on first run or if it changes
@st.cache_resource
def get_database(db_path):
    """Get a cached database instance.
    
    Args:
        db_path: Path to the SQLite database
        
    Returns:
        AttendanceSystemDB: Database instance
    """
    return AttendanceSystemDB(db_path)

# Initialize session state variables if they don't exist
if 'db_path' not in st.session_state:
    st.session_state.db_path = 'attendance.db'

# DATABASE RESET HANDLER
# Check if the database needs to be reset
db_path = st.session_state.db_path
reset_flag_path = f"{db_path}.reset"

if os.path.exists(reset_flag_path):
    # Display a notification
    st.info("Resetting database...")
    
    try:
        # Force close any existing database connections
        if 'db' in locals() or 'db' in globals():
            if hasattr(db, 'close_connection'):
                db.close_connection()
        
        # Also clear the thread_local storage which might hold connections
        import threading
        thread_local = threading.local()
        if hasattr(thread_local, 'conn'):
            try:
                thread_local.conn.close()
            except Exception as e:
                st.warning(f"Could not close thread_local connection: {e}")
            try:
                delattr(thread_local, 'conn')
            except:
                pass
        
        # Force garbage collection to help release file handles
        gc.collect()
        
        # Wait a moment to ensure connections are closed
        time.sleep(1)
        
        # Try to delete the database file
        if os.path.exists(db_path):
            try:
                # On Windows, sometimes we need to try multiple times with delays
                for attempt in range(3):
                    try:
                        os.remove(db_path)
                        st.success("Database has been reset successfully!")
                        break
                    except Exception as e:
                        if attempt < 2:  # Don't sleep on the last attempt
                            time.sleep(1)
                        else:
                            # If we still can't delete the file, try to empty it instead
                            try:
                                # Open the file in write mode, which truncates it to zero length
                                with open(db_path, 'w') as f:
                                    pass
                                st.success("Database has been emptied successfully!")
                            except Exception as e2:
                                st.error(f"Could not reset database: {e2}")
            except Exception as e:
                st.error(f"Error during database reset: {e}")
        
        # Remove the reset flag
        if os.path.exists(reset_flag_path):
            os.remove(reset_flag_path)
            
        # Clear any cached data
        if 'db_reset_needed' in st.session_state:
            del st.session_state.db_reset_needed
            
        # Clear the cache to force recreation of database
        st.cache_resource.clear()
            
    except Exception as e:
        st.error(f"Error during database reset: {e}")

# Get database connection using the cached resource
db = get_database(st.session_state.db_path)
# Create tables if they don't exist
db.create_tables()

# App title and description
st.title("📋 Attendance Management System")

# Sidebar for navigation
st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to", [
    "Dashboard", 
    "Mark Attendance", 
    "View Attendance", 
    "Reports", 
    "User Management",
    "Settings"
])

# Render the selected page
if page == "Dashboard":
    render_dashboard(db)
elif page == "Mark Attendance":
    render_mark_attendance(db)
elif page == "View Attendance":
    render_view_attendance(db)
elif page == "Reports":
    render_reports(db)
elif page == "User Management":
    render_user_management(db)
elif page == "Settings":
    render_settings(db)