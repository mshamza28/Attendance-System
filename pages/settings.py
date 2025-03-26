"""Settings page for the attendance system."""

import streamlit as st
import os
import tempfile
import shutil
import base64
from datetime import datetime


def render_settings(db):
    """Render the settings page.
    
    Args:
        db: Database connection
    """
    st.header("System Settings")
    
    # Database settings
    st.subheader("Database Settings")
    
    current_db = st.session_state.db_path
    st.info(f"Current database path: {current_db}")
    
    with st.form("db_settings_form"):
        new_db_path = st.text_input("Database Path", value=current_db)
        
        submitted = st.form_submit_button("Update Database Path")
        
        if submitted:
            if new_db_path != current_db:
                try:
                    # Close existing connection
                    db.close_connection()
                    
                    # Update the database path in session state
                    st.session_state.db_path = new_db_path
                    
                    # Create a new database instance with the new path
                    # The get_database function will be called on rerun
                    st.success(f"Database path updated to: {new_db_path}")
                    st.experimental_rerun()
                except Exception as e:
                    st.error(f"Error updating database path: {e}")
            else:
                st.info("Database path unchanged.")
    
    # About section
    st.subheader("About")
    st.markdown("""
    ### Attendance Management System
    
    A comprehensive system for tracking and analyzing attendance records.
    
    **Features:**
    - User management (students, employees, admins)
    - Daily attendance tracking
    - Detailed reports and analytics
    - Data visualization
    - Export capabilities
    
    **Version:** 1.0.0
    """)
    
    # Backup and reset options
    st.subheader("Backup & Reset")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("Export Database Backup"):
            try:
                # Create a copy of the database
                temp_dir = tempfile.mkdtemp()
                backup_path = os.path.join(temp_dir, "attendance_backup.db")
                
                shutil.copy2(st.session_state.db_path, backup_path)
                
                # Read the file and create a download link
                with open(backup_path, "rb") as f:
                    bytes_data = f.read()
                    b64 = base64.b64encode(bytes_data).decode()
                    
                    now = datetime.now().strftime("%Y%m%d_%H%M%S")
                    download_filename = f"attendance_backup_{now}.db"
                    
                    href = f'<a href="data:application/octet-stream;base64,{b64}" download="{download_filename}">Click to download the backup</a>'
                    st.markdown(href, unsafe_allow_html=True)
                    
                    st.success("Backup created successfully!")
            except Exception as e:
                st.error(f"Error creating backup: {e}")
    
    with col2:
        reset_db = st.button("Reset Database", type="primary")
        
        if reset_db:
            confirm = st.checkbox("I understand this will delete ALL data and cannot be undone.")
            
            if confirm:
                try:
                    # Close the current connection
                    db.close_connection()
                    
                    # Delete the database file
                    if os.path.exists(st.session_state.db_path):
                        os.remove(st.session_state.db_path)
                    
                    # Force recreation of the database on next rerun
                    st.experimental_rerun()
                    
                    st.success("Database reset successfully!")
                except Exception as e:
                    st.error(f"Error resetting database: {e}")
            else:
                st.warning("Please confirm the reset operation.")