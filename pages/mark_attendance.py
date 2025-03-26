"""Mark attendance page for the attendance system."""

import streamlit as st
from datetime import datetime, timedelta
from utils import format_dataframe_for_display, get_date_defaults


def render_mark_attendance(db):
    """Render the mark attendance page.
    
    Args:
        db: Database connection
    """
    st.header("Mark Attendance")
    
    try:
        # Get all users
        users_df = db.get_users()
        
        if users_df.empty:
            st.warning("No users found in the system. Please add users first.")
            return
        
        # Create form for marking attendance
        with st.form("mark_attendance_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                # Convert the users dataframe to a dictionary for the selectbox
                user_options = users_df.set_index('id')['name'].to_dict()
                user_id = st.selectbox("Select User", options=list(user_options.keys()), 
                                      format_func=lambda x: f"{user_options[x]} (ID: {x})")
                
                status = st.selectbox("Status", ["present", "absent", "late"])
                
            with col2:
                # Date selection (default to today)
                date = st.date_input("Date", value=datetime.now().date())
                
                # Only show time inputs if status is not "absent"
                if status != "absent":
                    check_in = st.time_input("Check-in Time", value=datetime.now().time())
                    check_out = st.time_input("Check-out Time", 
                                             value=(datetime.now() + timedelta(hours=8)).time())
                else:
                    check_in = None
                    check_out = None
            
            notes = st.text_area("Notes", height=100)
            
            submitted = st.form_submit_button("Mark Attendance")
            
            if submitted:
                try:
                    date_str = date.strftime('%Y-%m-%d')
                    
                    # Format times if they exist
                    check_in_str = check_in.strftime('%H:%M:%S') if check_in else None
                    check_out_str = check_out.strftime('%H:%M:%S') if check_out else None
                    
                    success = db.mark_attendance(
                        user_id, status, date_str, check_in_str, check_out_str, notes
                    )
                    
                    if success:
                        st.success(f"Attendance for {user_options[user_id]} marked successfully!")
                    else:
                        st.error("Failed to mark attendance.")
                except Exception as e:
                    st.error(f"Error: {e}")
        
        # Display recent attendance records
        st.subheader("Recent Attendance Records")
        today, week_ago, _ = get_date_defaults()
        
        recent_records = db.view_attendance(
            start_date=week_ago.strftime('%Y-%m-%d'),
            end_date=today.strftime('%Y-%m-%d')
        )
        
        if not recent_records.empty:
            styled_df = format_dataframe_for_display(recent_records)
            st.dataframe(styled_df)
        else:
            st.info("No recent attendance records found.")

    except Exception as e:
        st.error(f"Error: {e}")