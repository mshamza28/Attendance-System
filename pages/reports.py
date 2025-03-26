"""Reports page for the attendance system."""

import streamlit as st
import plotly.express as px
from utils import get_date_defaults


def render_reports(db):
    """Render the reports page.
    
    Args:
        db: Database connection
    """
    st.header("Attendance Reports")
    
    # Date range selection for reports
    col1, col2 = st.columns(2)
    today, _, first_day_of_month = get_date_defaults()
    
    with col1:
        start_date = st.date_input("Start Date", value=first_day_of_month, key="report_start_date")
    
    with col2:
        end_date = st.date_input("End Date", value=today, key="report_end_date")
    
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
        return
    
    try:
        # Generate report
        report_df = db.generate_report(
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