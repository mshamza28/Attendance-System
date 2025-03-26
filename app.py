"""Main application file for the Attendance Management System."""

import streamlit as st
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