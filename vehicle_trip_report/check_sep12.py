import sys, os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from database.db import get_connection
conn = get_connection()
cur = conn.cursor()
cur.execute("SELECT COUNT(*), SUM(CAST(net_weight AS NUMERIC)) FROM vehicle_trips WHERE trip_date='12-09-2026' AND slip_type='Input'")
row = cur.fetchone()
print(f"Sep 12 records: {row[0]}, Total weight: {row[1]}")
cur.close(); conn.close()
