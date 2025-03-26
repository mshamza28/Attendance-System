"""Settings page for the attendance system."""

import streamlit as st
import os
import tempfile
import shutil
import base64
import time
from datetime import datetime


def render_settings(db):
    """Render the settings page.
    
    Args:
        db: Database connection
    """
    st.header("System Settings")
    
    # Initialize session state variables if they don't exist
    if 'reset_stage' not in st.session_state:
        st.session_state.reset_stage = 0
    
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
                    st.rerun()
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
        # First stage: Show the initial reset button
        if st.session_state.reset_stage == 0:
            if st.button("Reset Database", type="primary"):
                st.session_state.reset_stage = 1
                st.rerun()
        
        # Second stage: Show confirmation
        elif st.session_state.reset_stage == 1:
            st.warning("⚠️ WARNING: This will delete ALL data and cannot be undone!")
            confirm = st.checkbox("I understand this will delete ALL data and cannot be undone.")
            
            col_cancel, col_confirm = st.columns(2)
            with col_cancel:
                if st.button("Cancel"):
                    st.session_state.reset_stage = 0
                    st.rerun()
            
            with col_confirm:
                if st.button("Confirm Reset", type="primary", disabled=not confirm):
                    try:
                        # Close the current connection
                        db.close_connection()
                        
                        # Add debug info about the database path
                        st.info(f"Attempting to reset database at: {st.session_state.db_path}")
                        
                        # Create a flag file to trigger reset on next startup
                        flag_path = f"{st.session_state.db_path}.reset"
                        with open(flag_path, 'w') as f:
                            f.write('reset')
                        
                        # Set a session flag to indicate reset is needed
                        st.session_state.db_reset_needed = True
                        
                        # Reset the stage
                        st.session_state.reset_stage = 0
                        
                        # Show success message
                        st.success("Database marked for reset. Application will restart...")
                        
                        # Add a short delay to show the success message
                        time.sleep(2)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error resetting database: {e}")
                        st.code(str(e))  # Show the full error details