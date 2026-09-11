import os
import sys
import psycopg2
from psycopg2.extras import RealDictCursor

# Ensure config can be imported if this is run directly
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DATABASE_URL, DB_PATH

def get_connection():
    """Returns a connection to the PostgreSQL database."""
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL environment variable is not set. Please set it in your .env file.")
    
    conn = psycopg2.connect(DATABASE_URL)
    return conn

def init_db():
    """Initializes the database schema."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS vehicle_trips (
            id SERIAL PRIMARY KEY,
            s_no INTEGER,
            rst_no TEXT NOT NULL,
            vehicle_no TEXT NOT NULL,
            net_weight TEXT NOT NULL,
            agency_name TEXT,
            reported_by TEXT,
            trip_date TEXT NOT NULL,
            trip_time TEXT,
            image_path TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            processing_unit TEXT DEFAULT 'Pratapgarh',
            slip_type TEXT DEFAULT 'Input',
            UNIQUE(rst_no, processing_unit, slip_type)
        )
    ''')
    
    conn.commit()
    cursor.close()
    conn.close()

if __name__ == "__main__":
    init_db()
    print(f"Database initialized.")
