import sqlite3
import pandas as pd
import threading
from typing import Optional, Dict, Any, List
from datetime import datetime

# Create a thread-local storage for database connections
thread_local = threading.local()

class AttendanceSystemDB:
    def __init__(self, db_path: str = 'attendance.db'):
        """Initialize the attendance system with a database path.
        
        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = db_path
        # Don't create a connection here - create it on demand in each thread
    
    def _get_db_connection(self) -> sqlite3.Connection:
        """Create and return a thread-specific database connection.
        
        Returns:
            sqlite3.Connection: Database connection object
        """
        # Check if this thread already has a connection
        if not hasattr(thread_local, 'conn'):
            # Create a new connection for this thread
            conn = sqlite3.connect(self.db_path)
            # Enable foreign keys constraint
            conn.execute("PRAGMA foreign_keys = ON")
            # Row factory for named column access
            conn.row_factory = sqlite3.Row
            thread_local.conn = conn
        
        return thread_local.conn
    
    def create_tables(self) -> None:
        """Create the necessary database tables if they don't exist."""
        conn = self._get_db_connection()
        try:
            cursor = conn.cursor()
            
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
            conn.commit()
        except sqlite3.Error as e:
            conn.rollback()
            raise

    def add_user(self, name: str, role: str) -> int:
        """Add a new user to the system."""
        conn = self._get_db_connection()
        if not name or not role:
            raise ValueError("Name and role cannot be empty")
            
        if role.lower() not in ('student', 'employee', 'admin'):
            raise ValueError("Role must be one of: student, employee, admin")
        
        try:
            cursor = conn.cursor()
            cursor.execute('INSERT INTO users (name, role) VALUES (?, ?)', 
                          (name.strip(), role.lower()))
            conn.commit()
            user_id = cursor.lastrowid
            return user_id
        except sqlite3.Error as e:
            conn.rollback()
            raise

    def mark_attendance(self, user_id: int, status: str, date: str, 
                        check_in: str = None, check_out: str = None, 
                        notes: str = None) -> bool:
        """Mark a user's attendance."""
        conn = self._get_db_connection()
        if status.lower() not in ('present', 'absent', 'late'):
            raise ValueError("Status must be one of: present, absent, late")
            
        # Verify user exists
        cursor = conn.cursor()
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
            
            conn.commit()
            return True
        except sqlite3.Error as e:
            conn.rollback()
            raise

    def view_attendance(self, start_date: Optional[str] = None, 
                       end_date: Optional[str] = None, 
                       user_id: Optional[int] = None,
                       status: Optional[str] = None) -> pd.DataFrame:
        """View attendance records with optional filters."""
        conn = self._get_db_connection()
        try:
            cursor = conn.cursor()
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
        """Generate an attendance report for a date range."""
        conn = self._get_db_connection()
        try:
            cursor = conn.cursor()
            
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
        """Get a list of all users in the system."""
        conn = self._get_db_connection()
        try:
            cursor = conn.cursor()
            
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
        """Delete a user from the system."""
        conn = self._get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM users WHERE id = ?', (user_id,))
            conn.commit()
            return cursor.rowcount > 0
        except sqlite3.Error as e:
            conn.rollback()
            raise
    
    def delete_attendance(self, user_id: int, date: str) -> bool:
        """Delete an attendance record."""
        conn = self._get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM attendance WHERE user_id = ? AND date = ?', 
                          (user_id, date))
            conn.commit()
            return cursor.rowcount > 0
        except sqlite3.Error as e:
            conn.rollback()
            raise

    def get_attendance_stats(self, start_date: str, end_date: str) -> Dict:
        """Get overall attendance statistics."""
        conn = self._get_db_connection()
        try:
            cursor = conn.cursor()
            
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
            if stats.get('total_records', 0) > 0:
                stats['overall_present_rate'] = round((stats['present_count'] / stats['total_records']) * 100, 2)
            else:
                stats['overall_present_rate'] = 0
                
            return stats
        except sqlite3.Error as e:
            raise

    def get_daily_stats(self, start_date: str, end_date: str) -> pd.DataFrame:
        """Get daily attendance statistics."""
        conn = self._get_db_connection()
        try:
            cursor = conn.cursor()
            
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
            
    def close_connection(self):
        """Close the database connection for the current thread."""
        if hasattr(thread_local, 'conn'):
            thread_local.conn.close()
            del thread_local.conn