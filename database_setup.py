# database_setup.py
import sqlite3
from datetime import datetime

def create_database():
    """Create the library management database with all required tables"""
    
    conn = sqlite3.connect('library_management.db')
    cursor = conn.cursor()
    
    # Books Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS books (
            book_id INTEGER PRIMARY KEY AUTOINCREMENT,
            rfid_tag TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            author TEXT,
            isbn TEXT,
            category TEXT,
            status TEXT DEFAULT 'available',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Users Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE,
            phone TEXT,
            face_encoding BLOB NOT NULL,
            registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_active INTEGER DEFAULT 1
        )
    ''')
    
    # Transactions Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
            book_id INTEGER,
            user_id INTEGER,
            rfid_tag TEXT,
            issue_date TIMESTAMP,
            due_date TIMESTAMP,
            return_date TIMESTAMP,
            status TEXT DEFAULT 'issued',
            issue_face_path TEXT,
            return_face_path TEXT,
            FOREIGN KEY (book_id) REFERENCES books(book_id),
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')
    
    # Activity Logs Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS activity_logs (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            transaction_id INTEGER,
            action TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            remarks TEXT,
            FOREIGN KEY (transaction_id) REFERENCES transactions(transaction_id)
        )
    ''')
    
    conn.commit()
    conn.close()
    print("Database created successfully!")

if __name__ == "__main__":
    create_database()
