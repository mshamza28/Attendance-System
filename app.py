import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
import os
import plotly.express as px
import plotly.graph_objects as go
from typing import Optional, Tuple, List, Dict, Any

class AttendanceSystemDB:
    def __init__(self, db_path: str = 'attendance.db'):
        """Initialize the attendance system with a database connection.
        
        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = db_path
        self.conn = self._get_db_connection()
        self.create_tables()
    
    def _get_db_connection(self) -> sqlite3.Connection:
        """Create and return a database connection with proper settings.
        
        Returns:
            sqlite3.Connection: Database connection object
        """
        conn = sqlite3.connect(self.db_path)
        # Enable foreign keys constraint
        conn.execute("PRAGMA foreign_keys = ON")
        # Row factory for named column access
        conn.row_factory = sqlite3.Row
        return conn
    
    def create_tables(self) -> None:
        """Create the necessary database tables if they don't exist."""
        try:
            cursor = self.conn.cursor()
            
            # Create users table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('student', 'employee', 'admin')),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            ''')

            # Create attendance table with proper constraints
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                date DATE NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('present', 'absent', 'late')),
                check_in TIME,
                check_out TIME,
                notes TEXT,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
                UNIQUE(user_id, date)
            )
            ''')
            self.conn.commit()
        except sqlite3.Error as e:
            st.error(f"Database error: {e}")
            self.conn.rollback()
            raise

    def add_user(self, name: str, role: str) -> int:
        """Add a new user to the system.
        
        Args:
            name: User's full name
            role: User's role (student, employee, admin)
            
        Returns:
            int: The new user's ID
            
        Raises:
            ValueError: If role is invalid
        """
        if not name or not role:
            raise ValueError("Name and role cannot be empty")
            
        if role.lower() not in ('student', 'employee', 'admin'):
            raise ValueError("Role must be one of: student, employee, admin")
        
        try:
            cursor = self.conn.cursor()
            cursor.execute('INSERT INTO users (name, role) VALUES (?, ?)', 
                          (name.strip(), role.lower()))
            self.conn.commit()
            user_id = cursor.lastrowid
            return user_id
        except sqlite3.Error as e:
            self.conn.rollback()
            raise

    def mark_attendance(self, user_id: int, status: str, date: str, 
                        check_in: str = None, check_out: str = None, 
                        notes: str = None) -> bool:
        """Mark a user's attendance.
        
        Args:
            user_id: ID of the user
            status: Attendance status (present, absent, late)
            date: Date for the attendance record (YYYY-MM-DD)
            check_in: Check-in time (HH:MM)
            check_out: Check-out time (HH:MM)
            notes: Additional notes
            
        Returns:
            bool: True if attendance was marked successfully
            
        Raises:
            ValueError: If status is invalid or user doesn't exist
        """
        if status.lower() not in ('present', 'absent', 'late'):
            raise ValueError("Status must be one of: present, absent, late")
            
        # Verify user exists
        cursor = self.conn.cursor()
        cursor.execute('SELECT id FROM users WHERE id = ?', (user_id,))
        if not cursor.fetchone():
            raise ValueError(f"User with ID {user_id} does not exist")
        
        try:
            # Check if attendance already exists for this date
            cursor.execute('''
            SELECT id FROM attendance 
            WHERE user_id = ? AND date = ?
            ''', (user_id, date))
            
            existing = cursor.fetchone()
            
            if existing:
                # Update existing record
                cursor.execute('''
                UPDATE attendance 
                SET status = ?, check_in = ?, check_out = ?, notes = ?
                WHERE id = ?
                ''', (status.lower(), check_in, check_out, notes, existing[0]))
            else:
                # Create new attendance record
                cursor.execute('''
                INSERT INTO attendance (user_id, date, status, check_in, check_out, notes)
                VALUES (?, ?, ?, ?, ?, ?)
                ''', (user_id, date, status.lower(), check_in, check_out, notes))
            
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            self.conn.rollback()
            raise

    def view_attendance(self, start_date: Optional[str] = None, 
                       end_date: Optional[str] = None, 
                       user_id: Optional[int] = None,
                       status: Optional[str] = None) -> pd.DataFrame:
        """View attendance records with optional filters.
        
        Args:
            start_date: Optional start date (YYYY-MM-DD)
            end_date: Optional end date (YYYY-MM-DD)
            user_id: Optional user ID to filter by
            status: Optional status to filter by
            
        Returns:
            pandas.DataFrame: Attendance records
        """
        try:
            cursor = self.conn.cursor()
            query = '''
            SELECT 
                u.id as user_id,
                u.name,
                u.role,
                a.date,
                a.status,
                a.check_in,
                a.check_out,
                a.notes,
                CASE 
                    WHEN a.check_out IS NOT NULL AND a.check_in IS NOT NULL 
                    THEN (strftime('%s', a.check_out) - strftime('%s', a.check_in))/3600.0 
                    ELSE NULL 
                END as hours_worked
            FROM attendance a
            JOIN users u ON a.user_id = u.id
            WHERE 1=1
            '''
            params = []
            
            if start_date:
                query += ' AND a.date >= ?'
                params.append(start_date)
            if end_date:
                query += ' AND a.date <= ?'
                params.append(end_date)
            if user_id:
                query += ' AND a.user_id = ?'
                params.append(user_id)
            if status:
                query += ' AND a.status = ?'
                params.append(status.lower())
                
            query += ' ORDER BY a.date DESC, u.name ASC'
            
            cursor.execute(query, params)
            records = cursor.fetchall()
            
            if not records:
                return pd.DataFrame()
            
            # Convert to DataFrame
            df = pd.DataFrame([dict(row) for row in records])
            
            return df
        except sqlite3.Error as e:
            raise

    def generate_report(self, start_date: str, end_date: str, role: Optional[str] = None) -> pd.DataFrame:
        """Generate an attendance report for a date range.
        
        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            role: Optional role to filter by
            
        Returns:
            pandas.DataFrame: Attendance report
        """
        try:
            cursor = self.conn.cursor()
            
            query = '''
            SELECT 
                u.id,
                u.name,
                u.role,
                COUNT(DISTINCT a.date) as total_days,
                COUNT(CASE WHEN a.status = 'present' THEN 1 END) as present_days,
                COUNT(CASE WHEN a.status = 'absent' THEN 1 END) as absent_days,
                COUNT(CASE WHEN a.status = 'late' THEN 1 END) as late_days,
                ROUND(AVG(CASE 
                    WHEN a.check_out IS NOT NULL AND a.check_in IS NOT NULL 
                    THEN (strftime('%s', a.check_out) - strftime('%s', a.check_in))/3600.0 
                    ELSE NULL 
                END), 2) as avg_hours_per_day
            FROM users u
            LEFT JOIN attendance a ON u.id = a.user_id AND a.date BETWEEN ? AND ?
            WHERE 1=1
            '''
            
            params = [start_date, end_date]
            
            if role:
                query += ' AND u.role = ?'
                params.append(role.lower())
                
            query += ' GROUP BY u.id ORDER BY u.name'
                
            cursor.execute(query, params)
            
            records = cursor.fetchall()
            
            if not records:
                return pd.DataFrame()
            
            # Convert to DataFrame
            df = pd.DataFrame([dict(row) for row in records])
            
            # Calculate attendance percentage
            if 'total_days' in df.columns and 'present_days' in df.columns:
                df['attendance_percent'] = df.apply(
                    lambda row: round((row['present_days'] / row['total_days']) * 100, 2) 
                    if row['total_days'] > 0 else 0, 
                    axis=1
                )
            
            return df
        except sqlite3.Error as e:
            raise

    def get_users(self, role: Optional[str] = None) -> pd.DataFrame:
        """Get a list of all users in the system.
        
        Args:
            role: Optional role to filter by
            
        Returns:
            pandas.DataFrame: All users
        """
        try:
            cursor = self.conn.cursor()
            
            query = 'SELECT id, name, role, created_at FROM users WHERE 1=1'
            params = []
            
            if role:
                query += ' AND role = ?'
                params.append(role.lower())
                
            query += ' ORDER BY name'
            
            cursor.execute(query, params)
            users = cursor.fetchall()
            
            if not users:
                return pd.DataFrame()
                
            # Convert to DataFrame
            df = pd.DataFrame([dict(row) for row in users])
            return df
        except sqlite3.Error as e:
            raise
    
    def delete_user(self, user_id: int) -> bool:
        """Delete a user from the system.
        
        Args:
            user_id: User ID to delete
            
        Returns:
            bool: True if successful
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute('DELETE FROM users WHERE id = ?', (user_id,))
            self.conn.commit()
            return cursor.rowcount > 0
        except sqlite3.Error as e:
            self.conn.rollback()
            raise
    
    def delete_attendance(self, user_id: int, date: str) -> bool:
        """Delete an attendance record.
        
        Args:
            user_id: User ID
            date: Date of the attendance record
            
        Returns:
            bool: True if successful
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute('DELETE FROM attendance WHERE user_id = ? AND date = ?', 
                          (user_id, date))
            self.conn.commit()
            return cursor.rowcount > 0
        except sqlite3.Error as e:
            self.conn.rollback()
            raise

    def get_attendance_stats(self, start_date: str, end_date: str) -> Dict:
        """Get overall attendance statistics.
        
        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            
        Returns:
            Dict: Statistics summary
        """
        try:
            cursor = self.conn.cursor()
            
            # Get total users
            cursor.execute('SELECT COUNT(*) FROM users')
            total_users = cursor.fetchone()[0]
            
            # Get attendance counts
            cursor.execute('''
            SELECT 
                COUNT(*) as total_records,
                SUM(CASE WHEN status = 'present' THEN 1 ELSE 0 END) as present_count,
                SUM(CASE WHEN status = 'absent' THEN 1 ELSE 0 END) as absent_count,
                SUM(CASE WHEN status = 'late' THEN 1 ELSE 0 END) as late_count
            FROM attendance
            WHERE date BETWEEN ? AND ?
            ''', (start_date, end_date))
            
            stats = dict(cursor.fetchone())
            stats['total_users'] = total_users
            
            # Calculate overall attendance rate
            if stats['total_records'] > 0:
                stats['overall_present_rate'] = round((stats['present_count'] / stats['total_records']) * 100, 2)
            else:
                stats['overall_present_rate'] = 0
                
            return stats
        except sqlite3.Error as e:
            raise

    def get_daily_stats(self, start_date: str, end_date: str) -> pd.DataFrame:
        """Get daily attendance statistics.
        
        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            
        Returns:
            pd.DataFrame: Daily statistics
        """
        try:
            cursor = self.conn.cursor()
            
            cursor.execute('''
            SELECT 
                date,
                COUNT(*) as total_records,
                SUM(CASE WHEN status = 'present' THEN 1 ELSE 0 END) as present_count,
                SUM(CASE WHEN status = 'absent' THEN 1 ELSE 0 END) as absent_count,
                SUM(CASE WHEN status = 'late' THEN 1 ELSE 0 END) as late_count
            FROM attendance
            WHERE date BETWEEN ? AND ?
            GROUP BY date
            ORDER BY date
            ''', (start_date, end_date))
            
            records = cursor.fetchall()
            
            if not records:
                return pd.DataFrame()
                
            # Convert to DataFrame
            df = pd.DataFrame([dict(row) for row in records])
            
            # Calculate daily rates
            if not df.empty:
                df['present_rate'] = df.apply(
                    lambda row: round((row['present_count'] / row['total_records']) * 100, 2),
                    axis=1
                )
                
            return df
        except sqlite3.Error as e:
            raise


# Initialize Streamlit app
st.set_page_config(
    page_title="Attendance Management System",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state variables if they don't exist
if 'db_path' not in st.session_state:
    st.session_state.db_path = 'attendance.db'
    
if 'db' not in st.session_state:
    st.session_state.db = AttendanceSystemDB(st.session_state.db_path)

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

# Function to format time display
def format_time(time_str):
    if not time_str:
        return "-"
    return time_str

# Function to create a date range
def date_range(start_date, end_date):
    delta = end_date - start_date
    days = [start_date + timedelta(days=i) for i in range(delta.days + 1)]
    return [day.strftime('%Y-%m-%d') for day in days]

# Dashboard page
if page == "Dashboard":
    st.header("Dashboard")
    
    # Date range selection
    col1, col2 = st.columns(2)
    with col1:
        today = datetime.now().date()
        default_start = today - timedelta(days=7)
        start_date = st.date_input("Start Date", value=default_start)
    with col2:
        end_date = st.date_input("End Date", value=today)
        
    if start_date > end_date:
        st.error("Error: Start date must be before end date")
    else:
        start_str = start_date.strftime('%Y-%m-%d')
        end_str = end_date.strftime('%Y-%m-%d')
        
        try:
            # Get overall stats
            stats = st.session_state.db.get_attendance_stats(start_str, end_str)
            
            # Display stat cards
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Total Users", stats.get('total_users', 0))
            with col2:
                st.metric("Present", stats.get('present_count', 0))
            with col3:
                st.metric("Absent", stats.get('absent_count', 0))
            with col4:
                st.metric("Late", stats.get('late_count', 0))
                
            # Display attendance rate with gauge
            overall_rate = stats.get('overall_present_rate', 0)
            
            fig = go.Figure(go.Indicator(
                mode = "gauge+number",
                value = overall_rate,
                title = {'text': "Overall Attendance Rate"},
                domain = {'x': [0, 1], 'y': [0, 1]},
                gauge = {
                    'axis': {'range': [0, 100]},
                    'bar': {'color': "darkblue"},
                    'steps': [
                        {'range': [0, 60], 'color': "red"},
                        {'range': [60, 80], 'color': "orange"},
                        {'range': [80, 100], 'color': "green"}
                    ],
                    'threshold': {
                        'line': {'color': "black", 'width': 4},
                        'thickness': 0.75,
                        'value': 90
                    }
                }
            ))
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Get daily stats
            daily_stats = st.session_state.db.get_daily_stats(start_str, end_str)
            
            if not daily_stats.empty:
                # Show daily trend
                st.subheader("Daily Attendance Trend")
                
                # First chart: attendance counts by status
                fig1 = px.bar(
                    daily_stats, 
                    x='date', 
                    y=['present_count', 'late_count', 'absent_count'],
                    title="Daily Attendance by Status",
                    labels={'value': 'Count', 'date': 'Date', 'variable': 'Status'},
                    color_discrete_map={
                        'present_count': 'green', 
                        'late_count': 'orange', 
                        'absent_count': 'red'
                    }
                )
                st.plotly_chart(fig1, use_container_width=True)
                
                # Second chart: attendance rate trend
                fig2 = px.line(
                    daily_stats, 
                    x='date', 
                    y='present_rate',
                    title="Daily Attendance Rate (%)",
                    labels={'present_rate': 'Attendance Rate (%)', 'date': 'Date'},
                    markers=True
                )
                fig2.add_shape(
                    type="line",
                    x0=daily_stats['date'].iloc[0],
                    y0=90,
                    x1=daily_stats['date'].iloc[-1],
                    y1=90,
                    line=dict(color="green", width=2, dash="dash")
                )
                st.plotly_chart(fig2, use_container_width=True)
            else:
                st.info("No attendance data available for the selected date range.")
            
        except Exception as e:
            st.error(f"Error loading dashboard data: {e}")

# Mark Attendance page
elif page == "Mark Attendance":
    st.header("Mark Attendance")
    
    try:
        # Get all users
        users_df = st.session_state.db.get_users()
        
        if users_df.empty:
            st.warning("No users found in the system. Please add users first.")
        else:
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
                        
                        success = st.session_state.db.mark_attendance(
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
            today = datetime.now().date()
            week_ago = today - timedelta(days=7)
            
            recent_records = st.session_state.db.view_attendance(
                start_date=week_ago.strftime('%Y-%m-%d'),
                end_date=today.strftime('%Y-%m-%d')
            )
            
            if not recent_records.empty:
                # Format the times for display
                if 'check_in' in recent_records.columns:
                    recent_records['check_in'] = recent_records['check_in'].apply(format_time)
                if 'check_out' in recent_records.columns:
                    recent_records['check_out'] = recent_records['check_out'].apply(format_time)
                    
                # Format hours_worked to 2 decimal places
                if 'hours_worked' in recent_records.columns:
                    recent_records['hours_worked'] = recent_records['hours_worked'].apply(
                        lambda x: f"{x:.2f}" if pd.notnull(x) else "-"
                    )
                
                # Apply color formatting based on status
                def highlight_status(row):
                    if row.status == 'present':
                        return ['background-color: #d4edda'] * len(row)
                    elif row.status == 'absent':
                        return ['background-color: #f8d7da'] * len(row)
                    elif row.status == 'late':
                        return ['background-color: #fff3cd'] * len(row)
                    return [''] * len(row)
                
                styled_df = recent_records.style.apply(highlight_status, axis=1)
                st.dataframe(styled_df)
            else:
                st.info("No recent attendance records found.")
    
    except Exception as e:
        st.error(f"Error: {e}")

# View Attendance page
elif page == "View Attendance":
    st.header("View Attendance Records")
    
    # Create filters
    col1, col2 = st.columns(2)
    
    with col1:
        # Date range filter
        start_date = st.date_input("Start Date", value=datetime.now().date() - timedelta(days=30))
        end_date = st.date_input("End Date", value=datetime.now().date())
    
    with col2:
        # User filter
        try:
            users_df = st.session_state.db.get_users()
            
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
        else:
            try:
                attendance_df = st.session_state.db.view_attendance(
                    start_date=start_date.strftime('%Y-%m-%d'),
                    end_date=end_date.strftime('%Y-%m-%d'),
                    user_id=selected_user,
                    status=selected_status
                )
                
                if not attendance_df.empty:
                    # Format the dataframe for display
                    if 'check_in' in attendance_df.columns:
                        attendance_df['check_in'] = attendance_df['check_in'].apply(format_time)
                    if 'check_out' in attendance_df.columns:
                        attendance_df['check_out'] = attendance_df['check_out'].apply(format_time)
                        
                    # Format hours_worked to 2 decimal places
                    if 'hours_worked' in attendance_df.columns:
                        attendance_df['hours_worked'] = attendance_df['hours_worked'].apply(
                            lambda x: f"{x:.2f}" if pd.notnull(x) else "-"
                        )
                    
                    # Add a delete button column
                    def highlight_status(row):
                        if row.status == 'present':
                            return ['background-color: #d4edda'] * len(row)
                        elif row.status == 'absent':
                            return ['background-color: #f8d7da'] * len(row)
                        elif row.status == 'late':
                            return ['background-color: #fff3cd'] * len(row)
                        return [''] * len(row)
                    
                    styled_df = attendance_df.style.apply(highlight_status, axis=1)
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

# Reports page
elif page == "Reports":
    st.header("Attendance Reports")
    
    # Date range selection for reports
    col1, col2 = st.columns(2)
    
    with col1:
        today = datetime.now().date()
        first_day_of_month = today.replace(day=1)
        start_date = st.date_input("Start Date", value=first_day_of_month)
    
    with col2:
        end_date = st.date_input("End Date", value=today)
    
    # Role filter
    try:
        roles = ["All Roles", "student", "employee", "admin"]
        selected_role = st.selectbox("Filter by Role", roles)
        
        if selected_role == "All Roles":
            selected_role = None
    except Exception as e:
        st.error(f"Error: {e}")
        selected_role = None
    
    if start_date > end_date:
        st.error("Error: Start date must be before end date")
    else:
        try:
            # Generate report
            report_df = st.session_state.db.generate_report(
                start_date.strftime('%Y-%m-%d'),
                end_date.strftime('%Y-%m-%d'),
                role=selected_role
            )
            
            if not report_df.empty:
                st.subheader(f"Attendance Report ({start_date} to {end_date})")
                
                # Display summary metrics
                metrics_cols = st.columns(4)
                with metrics_cols[0]:
                    st.metric("Total Users", len(report_df))
                with metrics_cols[1]:
                    avg_present = report_df['present_days'].mean()
                    st.metric("Avg. Present Days", f"{avg_present:.1f}")
                with metrics_cols[2]:
                    avg_absent = report_df['absent_days'].mean()
                    st.metric("Avg. Absent Days", f"{avg_absent:.1f}")
                with metrics_cols[3]:
                    avg_attendance = report_df['attendance_percent'].mean()
                    st.metric("Avg. Attendance %", f"{avg_attendance:.1f}%")
                
                # Display the report as a table
                st.dataframe(report_df.style.background_gradient(subset=['attendance_percent'], cmap='RdYlGn'))
                
                # Visualizations
                st.subheader("Attendance Visualization")
                
                # Bar chart of present/absent/late days by user
                chart_data = report_df.melt(
                    id_vars=['name', 'role'],
                    value_vars=['present_days', 'absent_days', 'late_days'],
                    var_name='status_type',
                    value_name='days'
                )
                
                fig = px.bar(
                    chart_data, 
                    x='name', 
                    y='days',
                    color='status_type',
                    barmode='group',
                    title="Attendance Breakdown by User",
                    labels={'name': 'User', 'days': 'Days', 'status_type': 'Status'},
                    color_discrete_map={
                        'present_days': 'green',
                        'absent_days': 'red',
                        'late_days': 'orange'
                    }
                )
                st.plotly_chart(fig, use_container_width=True)
                
                # Attendance percentage chart
                fig2 = px.bar(
                    report_df,
                    x='name',
                    y='attendance_percent',
                    color='attendance_percent',
                    color_continuous_scale='RdYlGn',
                    title="Attendance Percentage by User",
                    labels={'name': 'User', 'attendance_percent': 'Attendance %'}
                )
                fig2.add_shape(
                    type="line",
                    x0=-0.5,
                    y0=90,
                    x1=len(report_df) - 0.5,
                    y1=90,
                    line=dict(color="black", width=2, dash="dash")
                )
                st.plotly_chart(fig2, use_container_width=True)
                
                # Export options
                st.download_button(
                    label="Export Report to CSV",
                    data=report_df.to_csv(index=False).encode('utf-8'),
                    file_name=f"attendance_report_{start_date}_to_{end_date}.csv",
                    mime="text/csv"
                )
            else:
                st.info("No attendance data found for the selected period.")
                
        except Exception as e:
            st.error(f"Error generating report: {e}")
            
# User Management page
elif page == "User Management":
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
            users_df = st.session_state.db.get_users(role=filter_role)
            
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
                                success = st.session_state.db.delete_user(delete_user_id)
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
                        user_id = st.session_state.db.add_user(name, role)
                        st.success(f"User {name} added successfully with ID: {user_id}")
                    except Exception as e:
                        st.error(f"Error adding user: {e}")
    
    # User Statistics tab
    with user_tabs[2]:
        st.subheader("User Statistics")
        
        try:
            # Get all users
            all_users = st.session_state.db.get_users()
            
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

# Settings page
elif page == "Settings":
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
                    # Reinitialize the database connection
                    st.session_state.db_path = new_db_path
                    st.session_state.db = AttendanceSystemDB(new_db_path)
                    st.success(f"Database path updated to: {new_db_path}")
                except Exception as e:
                    st.error(f"Error updating database path: {e}")
                    # Revert to the previous path
                    st.session_state.db_path = current_db
                    st.session_state.db = AttendanceSystemDB(current_db)
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
                import shutil
                import tempfile
                import base64
                from datetime import datetime
                
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
                    st.session_state.db.conn.close()
                    
                    # Delete the database file
                    if os.path.exists(st.session_state.db_path):
                        os.remove(st.session_state.db_path)
                    
                    # Reinitialize the database
                    st.session_state.db = AttendanceSystemDB(st.session_state.db_path)
                    
                    st.success("Database reset successfully!")
                except Exception as e:
                    st.error(f"Error resetting database: {e}")
            else:
                st.warning("Please confirm the reset operation.")
