import psycopg2
from psycopg2.extras import RealDictCursor
import sys

# Connection details
OLD_DB_URL = "postgresql://postgres.uyefffibiublwzodjqmk:Arshlankhan%40786@aws-0-ap-southeast-2.pooler.supabase.com:5432/postgres"
NEW_DB_URL = "postgresql://postgres.pyethzgoepoxqlbkmbft:Arshlankhan%40786@aws-0-ap-south-1.pooler.supabase.com:5432/postgres"

def init_new_db(cursor):
    print("Initializing schema on new database...")
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

def main():
    print("Connecting to OLD database (Sydney)...")
    try:
        old_conn = psycopg2.connect(OLD_DB_URL)
        old_cursor = old_conn.cursor(cursor_factory=RealDictCursor)
    except Exception as e:
        print(f"Failed to connect to old database: {e}")
        sys.exit(1)

    print("Connecting to NEW database (Mumbai)...")
    try:
        new_conn = psycopg2.connect(NEW_DB_URL)
        new_cursor = new_conn.cursor()
    except Exception as e:
        print(f"Failed to connect to new database: {e}")
        sys.exit(1)

    # Init schema
    init_new_db(new_cursor)
    new_conn.commit()

    print("Fetching records from old database...")
    old_cursor.execute("SELECT * FROM vehicle_trips")
    records = old_cursor.fetchall()
    
    if not records:
        print("No records found in the old database to migrate.")
    else:
        print(f"Found {len(records)} records. Migrating...")
        
        insert_query = '''
            INSERT INTO vehicle_trips 
            (id, s_no, rst_no, vehicle_no, net_weight, agency_name, reported_by, trip_date, trip_time, image_path, created_at, processing_unit, slip_type)
            VALUES (%(id)s, %(s_no)s, %(rst_no)s, %(vehicle_no)s, %(net_weight)s, %(agency_name)s, %(reported_by)s, %(trip_date)s, %(trip_time)s, %(image_path)s, %(created_at)s, %(processing_unit)s, %(slip_type)s)
            ON CONFLICT (id) DO NOTHING;
        '''
        
        migrated_count = 0
        for rec in records:
            try:
                new_cursor.execute(insert_query, rec)
                migrated_count += 1
            except Exception as e:
                print(f"Error migrating record {rec['id']}: {e}")
                new_conn.rollback() # Rollback the failed transaction block
                
        # Fix sequence id for new inserts
        if migrated_count > 0:
            print("Updating primary key sequence...")
            new_cursor.execute("SELECT setval(pg_get_serial_sequence('vehicle_trips', 'id'), coalesce(max(id), 1), max(id) IS NOT null) FROM vehicle_trips;")
            
        new_conn.commit()
        print(f"Successfully migrated {migrated_count} records to the new database!")

    old_cursor.close()
    old_conn.close()
    new_cursor.close()
    new_conn.close()
    print("Migration complete.")

if __name__ == "__main__":
    main()
