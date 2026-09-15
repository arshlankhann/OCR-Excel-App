import os, sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from database.db import get_connection
import pandas as pd

def check_db():
    conn = get_connection()
    try:
        query = "SELECT DISTINCT processing_unit, agency_name FROM vehicle_trips ORDER BY processing_unit, agency_name"
        df = pd.read_sql(query, conn)
        print(df)
        
        # Also let's check which dates have processing_unit='Other'
        query2 = "SELECT trip_date, processing_unit, agency_name, SUM(CAST(net_weight AS INTEGER)) as wt FROM vehicle_trips GROUP BY trip_date, processing_unit, agency_name ORDER BY trip_date"
        df2 = pd.read_sql(query2, conn)
        print(df2[df2['processing_unit'] == 'Other'])
    finally:
        conn.close()

if __name__ == "__main__":
    check_db()
