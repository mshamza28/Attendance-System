"""View attendance page for the attendance system."""

import streamlit as st
from utils import format_dataframe_for_display, get_date_defaults
from datetime import datetime, timedelta


def render_view_attendance(db):
    """Render the view attendance page.
    
    Args:
        db: Database connection
    """
    st.header("View Attendance Records")
    
    # Create filters
    col1, col2 = st.columns(2)
    today, _, _ = get_date_defaults()
    month_ago = today - timedelta(days=30)
    
    with col1:
        # Date range filter
        start_date = st.date_input("Start Date", value=month_ago, key="view_start_date")
        end_date = st.date_input("End Date", value=today, key="view_end_date")
    
    with col2:
        # User filter
        try:
            users_df = db.get_users()
            
            if not users_df.empty:
                user_options = {"All Users": None}
                user_options.update(users_df.set_index('id')['name'].to_dict())
                
                selected_user = st.selectbox(
                    "Filter by User", 
                    options=["All Users"] + list(users_df['id']),
                    format_func=lambda x: user_options.get(x, x) if x != "All Users" else x
                )
                
                if selected_user == "All Users":
                    selected_user = None
            else:
                selected_user = None
                st.warning("No users found in the system.")
            
            # Status filter
            status_options = ["All Statuses", "present", "absent", "late"]
            selected_status = st.selectbox("Filter by Status", status_options)
            
            if selected_status == "All Statuses":
                selected_status = None
        
        except Exception as e:
            st.error(f"Error loading user data: {e}")
            selected_user = None
            selected_status = None
    
    # Fetch and display attendance based on filters
    if start_date and end_date:
        if start_date > end_date:
            st.error("Error: Start date must be before end date")
            return
        
        try:
            attendance_df = db.view_attendance(
                start_date=start_date.strftime('%Y-%m-%d'),
                end_date=end_date.strftime('%Y-%m-%d'),
                user_id=selected_user,
                status=selected_status
            )
            
            if not attendance_df.empty:
                styled_df = format_dataframe_for_display(attendance_df)
                st.dataframe(styled_df)
                
                # Export options
                st.download_button(
                    label="Export to CSV",
                    data=attendance_df.to_csv(index=False).encode('utf-8'),
                    file_name=f"attendance_{start_date}_to_{end_date}.csv",
                    mime="text/csv"
                )
            else:
                st.info("No attendance records found for the selected filters.")
        
        except Exception as e:
            st.error(f"Error retrieving attendance data: {e}")