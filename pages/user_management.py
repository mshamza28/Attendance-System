"""User management page for the attendance system."""

import streamlit as st
import pandas as pd
import plotly.express as px


def render_user_management(db):
    """Render the user management page.
    
    Args:
        db: Database connection
    """
    st.header("User Management")
    
    # Tabs for different user management functions
    user_tabs = st.tabs(["All Users", "Add User", "User Statistics"])
    
    # All Users tab
    with user_tabs[0]:
        st.subheader("User List")
        
        # Role filter
        roles = ["All Roles", "student", "employee", "admin"]
        role_filter = st.selectbox("Filter by Role", roles, key="role_filter_list")
        
        filter_role = None if role_filter == "All Roles" else role_filter
        
        try:
            users_df = db.get_users(role=filter_role)
            
            if not users_df.empty:
                # Format the timestamps
                if 'created_at' in users_df.columns:
                    users_df['created_at'] = pd.to_datetime(users_df['created_at']).dt.strftime('%Y-%m-%d %H:%M')
                
                # Add actions column
                st.dataframe(users_df)
                
                # User deletion
                with st.expander("Delete User"):
                    delete_user_id = st.selectbox(
                        "Select User to Delete",
                        options=users_df['id'],
                        format_func=lambda x: f"{users_df[users_df['id'] == x]['name'].iloc[0]} (ID: {x})"
                    )
                    
                    if st.button("Delete User", type="primary", key="delete_user_btn"):
                        confirm = st.checkbox("I understand this will delete all attendance records for this user and cannot be undone.")
                        
                        if confirm:
                            try:
                                success = db.delete_user(delete_user_id)
                                if success:
                                    st.success("User deleted successfully!")
                                    st.experimental_rerun()
                                else:
                                    st.error("Failed to delete user.")
                            except Exception as e:
                                st.error(f"Error: {e}")
                        else:
                            st.warning("Please confirm the deletion.")
            else:
                st.info("No users found with the selected filter.")
                
        except Exception as e:
            st.error(f"Error retrieving user data: {e}")
    
    # Add User tab
    with user_tabs[1]:
        st.subheader("Add New User")
        
        with st.form("add_user_form"):
            name = st.text_input("Full Name")
            role = st.selectbox("Role", ["student", "employee", "admin"])
            
            submitted = st.form_submit_button("Add User")
            
            if submitted:
                if not name:
                    st.error("Name cannot be empty.")
                else:
                    try:
                        user_id = db.add_user(name, role)
                        st.success(f"User {name} added successfully with ID: {user_id}")
                    except Exception as e:
                        st.error(f"Error adding user: {e}")
    
    # User Statistics tab
    with user_tabs[2]:
        st.subheader("User Statistics")
        
        try:
            # Get all users
            all_users = db.get_users()
            
            if not all_users.empty:
                # Display basic stats
                total_users = len(all_users)
                role_counts = all_users['role'].value_counts()
                
                # Create metrics
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric("Total Users", total_users)
                
                with col2:
                    student_count = role_counts.get('student', 0)
                    st.metric("Students", student_count)
                
                with col3:
                    employee_count = role_counts.get('employee', 0)
                    st.metric("Employees", employee_count)
                
                # Chart for roles
                fig = px.pie(
                    all_users,
                    names='role',
                    title="User Distribution by Role",
                    color='role',
                    color_discrete_map={
                        'student': '#36A2EB',
                        'employee': '#FFCE56',
                        'admin': '#FF6384'
                    }
                )
                st.plotly_chart(fig, use_container_width=True)
                
                # User creation timeline
                if 'created_at' in all_users.columns:
                    all_users['created_at'] = pd.to_datetime(all_users['created_at'])
                    all_users['created_date'] = all_users['created_at'].dt.date
                    
                    # Group by creation date
                    creation_counts = all_users.groupby('created_date').size().reset_index(name='count')
                    creation_counts['cumulative'] = creation_counts['count'].cumsum()
                    
                    # Line chart for user growth
                    fig2 = px.line(
                        creation_counts,
                        x='created_date',
                        y='cumulative',
                        title="User Growth Over Time",
                        labels={'created_date': 'Date', 'cumulative': 'Total Users'},
                        markers=True
                    )
                    st.plotly_chart(fig2, use_container_width=True)
            else:
                st.info("No users found in the system.")
                
        except Exception as e:
            st.error(f"Error retrieving user statistics: {e}")