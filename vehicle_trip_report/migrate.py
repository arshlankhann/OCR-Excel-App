import sqlite3
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from config import DB_PATH

def migrate_db():
    print(f"Migrating database at {DB_PATH}")
    if not os.path.exists(DB_PATH):
        print("Database does not exist yet. No migration needed.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check if vehicle_trips exists
    cursor.execute("SELECT count(name) FROM sqlite_master WHERE type='table' AND name='vehicle_trips'")
    if cursor.fetchone()[0] == 0:
        print("Table vehicle_trips does not exist. No migration needed.")
        return

    # Check the schema to see if we need to migrate
    # If the unique constraint is already (rst_no, processing_unit), we don't need to do anything
    cursor.execute("PRAGMA index_list('vehicle_trips')")
    indexes = cursor.fetchall()
    
    has_old_unique = False
    for idx in indexes:
        if idx[2] == 1: # unique index
            cursor.execute(f"PRAGMA index_info('{idx[1]}')")
            cols = cursor.fetchall()
            col_names = [c[2] for c in cols]
            if col_names == ['rst_no']:
                has_old_unique = True
            elif col_names == ['rst_no', 'processing_unit', 'slip_type']:
                print("Database already has the correct unique constraint with slip_type. No migration needed.")
                return

    print("Recreating table to update unique constraint and add slip_type...")
    
    # Recreate table with new constraints
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS vehicle_trips_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    
    # Check if old table has processing_unit column
    cursor.execute("PRAGMA table_info('vehicle_trips')")
    columns = [col[1] for col in cursor.fetchall()]
    
    if 'processing_unit' in columns and 'slip_type' not in columns:
        cursor.execute("INSERT INTO vehicle_trips_new (id, s_no, rst_no, vehicle_no, net_weight, agency_name, reported_by, trip_date, trip_time, image_path, created_at, processing_unit, slip_type) SELECT id, s_no, rst_no, vehicle_no, net_weight, agency_name, reported_by, trip_date, trip_time, image_path, created_at, processing_unit, 'Input' FROM vehicle_trips")
    elif 'slip_type' in columns:
        cursor.execute("INSERT INTO vehicle_trips_new (id, s_no, rst_no, vehicle_no, net_weight, agency_name, reported_by, trip_date, trip_time, image_path, created_at, processing_unit, slip_type) SELECT id, s_no, rst_no, vehicle_no, net_weight, agency_name, reported_by, trip_date, trip_time, image_path, created_at, processing_unit, slip_type FROM vehicle_trips")
    else:
        cursor.execute("INSERT INTO vehicle_trips_new (id, s_no, rst_no, vehicle_no, net_weight, agency_name, reported_by, trip_date, trip_time, image_path, created_at, slip_type) SELECT id, s_no, rst_no, vehicle_no, net_weight, agency_name, reported_by, trip_date, trip_time, image_path, created_at, 'Input' FROM vehicle_trips")
    
    cursor.execute("DROP TABLE vehicle_trips")
    cursor.execute("ALTER TABLE vehicle_trips_new RENAME TO vehicle_trips")
    
    conn.commit()
    conn.close()
    print("Migration completed successfully.")

if __name__ == "__main__":
    migrate_db()
