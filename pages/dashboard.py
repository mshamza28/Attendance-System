"""Dashboard page for the attendance system."""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from utils import get_date_defaults


def render_dashboard(db):
    """Render the dashboard page.
    
    Args:
        db: Database connection
    """
    st.header("Dashboard")
    
    # Date range selection
    col1, col2 = st.columns(2)
    today, week_ago, _ = get_date_defaults()
    
    with col1:
        start_date = st.date_input("Start Date", value=week_ago, key="dashboard_start_date")
    with col2:
        end_date = st.date_input("End Date", value=today, key="dashboard_end_date")
        
    if start_date > end_date:
        st.error("Error: Start date must be before end date")
        return
    
    start_str = start_date.strftime('%Y-%m-%d')
    end_str = end_date.strftime('%Y-%m-%d')
    
    try:
        # Get overall stats
        stats = db.get_attendance_stats(start_str, end_str)
        
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
        daily_stats = db.get_daily_stats(start_str, end_str)
        
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