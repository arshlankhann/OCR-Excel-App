import os, sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from database.db import get_connection

def update_agency():
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT COUNT(*) FROM vehicle_trips WHERE agency_name IN ('Government', 'Gov Vehicle')")
        count = cur.fetchone()[0]
        print(f"Found {count} records with agency_name 'Government' or 'Gov Vehicle'")
        
        if count > 0:
            cur.execute("UPDATE vehicle_trips SET agency_name = 'Govt Vehicle' WHERE agency_name IN ('Government', 'Gov Vehicle')")
            conn.commit()
            print(f"Successfully updated {count} records.")
        else:
            print("No records needed updating.")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    update_agency()
