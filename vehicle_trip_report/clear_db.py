import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from database.db import get_connection

def clear_db():
    print("Clearing all data from vehicle_trips table...")
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("TRUNCATE TABLE vehicle_trips RESTART IDENTITY;")
        conn.commit()
        print("Database cleared successfully.")
    except Exception as e:
        print(f"Error clearing database: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    clear_db()
