import os
import sys
import argparse
import math

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from database.db import get_connection

TRIP_TIME   = "08:00:00"
SLIP_TYPE   = "Input"

# Date mapping to data
# (agency_name, total_weight_kg)
DATA_MAP = {
    "01": [("SVN", 122790), ("J.P Bros", 313790), ("V S Waste", 142060)],
    "02": [("V S Waste", 131600), ("Tractor", 31450)],
    "03": [("V S Waste", 71260), ("Tractor", 39670)],
    "04": [("SVN", 389000), ("J.P Bros", 307580), ("V S Waste", 138730), ("Tractor", 32450)],
    "05": [("SVN", 428920), ("J.P Bros", 291780), ("V S Waste", 108180), ("Tractor", 29190)],
    "06": [("SVN", 548690), ("J.P Bros", 373760), ("V S Waste", 128500), ("Tractor", 31260)],
    "07": [("SVN", 164990), ("J.P Bros", 126340), ("V S Waste", 148580), ("Tractor", 19990)],
    "08": [("SVN", 258670), ("J.P Bros", 105470), ("Government", 46520), ("V S Waste", 211320), ("Tractor", 169720)],
    "09": [("SVN", 231730), ("J.P Bros", 136070), ("V S Waste", 141290), ("Tractor", 135800)],
    "10": [("SVN", 228990), ("J.P Bros", 114060), ("Government", 16890), ("V S Waste", 148860), ("Tractor", 29880)],
    "11": [("SVN", 162130), ("J.P Bros", 129830), ("V S Waste", 84180), ("Tractor", 32630)],
}

AGENCY_META = {
    "SVN": ("Pratapgarh", "Krishan JE"),
    "J.P Bros": ("Pratapgarh", "Krishan JE"),
    "Government": ("Pratapgarh", "Krishan JE"),
    "V S Waste": ("Mujeri", "V S Waste"),
    "Tractor": ("Mujeri", "Tractor")
}

# Function to get approx number of trips based on average weights from other manual insertions
def get_num_trips(agency, total_wt):
    if total_wt == 0:
        return 0
    if agency == "SVN":
        avg = 15000
    elif agency == "J.P Bros":
        avg = 22000
    elif agency == "Government":
        avg = 11000
    elif agency == "V S Waste":
        avg = 13000
    elif agency == "Tractor":
        avg = 1500
    else:
        avg = 15000
    
    trips = max(1, round(total_wt / avg))
    return trips


def build_records():
    records = []
    rst_counter = 80100  # distinct range

    for day_str, entries in DATA_MAP.items():
        trip_date = f"{day_str}-09-2026"
        for agency, total_wt in entries:
            unit, reporter = AGENCY_META[agency]
            num_trips = get_num_trips(agency, total_wt)
            
            if num_trips == 0:
                continue
                
            base_wt = total_wt // num_trips
            remainder = total_wt - base_wt * num_trips
            
            for i in range(num_trips):
                wt = base_wt + (1 if i == 0 else 0) * remainder
                rst_no = f"M{rst_counter}"
                rst_counter += 1
                
                records.append({
                    "rst_no":          rst_no,
                    "vehicle_no":      "MANUAL",
                    "net_weight":      str(wt),
                    "agency_name":     agency,
                    "reported_by":     reporter,
                    "trip_date":       trip_date,
                    "trip_time":       TRIP_TIME,
                    "image_path":      None,
                    "processing_unit": unit,
                    "slip_type":       SLIP_TYPE,
                })
    return records


def run(dry_run=False, overwrite=False):
    records = build_records()

    print(f"\n{'DRY RUN - ' if dry_run else ''}Sep 1-11 Summary Import")
    print(f"Total records generated to insert: {len(records)}")

    if dry_run:
        print("\nDRY RUN complete - nothing inserted.")
        return

    conn = get_connection()
    conn.autocommit = True
    cur = conn.cursor()

    try:
        inserted = 0
        errors = 0
        
        for day_str in DATA_MAP.keys():
            trip_date = f"{day_str}-09-2026"
            
            cur.execute("SELECT COUNT(*) FROM vehicle_trips WHERE trip_date=%s AND slip_type=%s",
                        (trip_date, SLIP_TYPE))
            existing = cur.fetchone()[0]
            
            if existing > 0:
                if overwrite:
                    cur.execute("DELETE FROM vehicle_trips WHERE trip_date=%s AND slip_type=%s",
                                (trip_date, SLIP_TYPE))
                    print(f"  Cleared {existing} existing records for {trip_date}")
                else:
                    print(f"  Data for {trip_date} already exists ({existing} records). Skipping this date.")
                    continue

            # get next s_no
            cur.execute("SELECT MAX(s_no) FROM vehicle_trips WHERE trip_date=%s AND slip_type=%s",
                        (trip_date, SLIP_TYPE))
            s_no = (cur.fetchone()[0] or 0) + 1
            
            # insert for this date
            day_records = [r for r in records if r["trip_date"] == trip_date]
            
            for rec in day_records:
                try:
                    cur.execute("""
                        INSERT INTO vehicle_trips
                            (s_no, rst_no, vehicle_no, net_weight, agency_name, reported_by,
                             trip_date, trip_time, image_path, processing_unit, slip_type)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    """, (s_no, rec["rst_no"], rec["vehicle_no"], rec["net_weight"],
                          rec["agency_name"], rec["reported_by"], rec["trip_date"],
                          rec["trip_time"], rec["image_path"], rec["processing_unit"],
                          rec["slip_type"]))
                    s_no += 1
                    inserted += 1
                except Exception as e:
                    errors += 1
                    print(f"  ERROR {rec['rst_no']}: {e}")
                    
        conn.commit()
        print(f"\nDone! Inserted: {inserted} | Errors: {errors}")

    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run",   action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    run(dry_run=args.dry_run, overwrite=args.overwrite)
