import os, sys, argparse
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from database.db import get_connection

TRIP_DATE   = "11-09-2026"
TRIP_TIME   = "08:00:00"
SLIP_TYPE   = "Input"

# (agency_name, total_weight_kg, num_trips, processing_unit, reported_by)
SEP11_DATA = [
    ("V S Waste",   84180,  6, "Mujeri",     "V S Waste"),
    ("SVN",        162130, 10, "Pratapgarh", "Krishan JE"),
    ("Tractor",     32630, 25, "Mujeri",     "Tractor"),
    ("J.P Bros",   129830,  6, "Pratapgarh", "Krishan JE"),
]

def build_records():
    records = []
    rst_counter = 93000  # distinct prefix
    for agency, total_wt, num_trips, unit, reporter in SEP11_DATA:
        base_wt   = total_wt // num_trips
        remainder = total_wt  - base_wt * num_trips
        for i in range(num_trips):
            wt = base_wt + (remainder if i == 0 else 0)
            records.append({
                "rst_no":          f"M{rst_counter}",
                "vehicle_no":      "MANUAL",
                "net_weight":      str(wt),
                "agency_name":     agency,
                "reported_by":     reporter,
                "trip_date":       TRIP_DATE,
                "trip_time":       TRIP_TIME,
                "image_path":      None,
                "processing_unit": unit,
                "slip_type":       SLIP_TYPE,
            })
            rst_counter += 1
    return records

def run(dry_run=False, overwrite=False):
    records = build_records()
    print(f"\n{'DRY RUN - ' if dry_run else ''}Sep 11 Summary Update")
    print("=" * 60)
    for agency, total_wt, num_trips, unit, _ in SEP11_DATA:
        print(f"{agency:<15} {unit:<12} {num_trips:>6} {total_wt:>14,}")
    print("-" * 50)
    print(f"Total records to insert: {len(records)}")

    if dry_run: return

    conn = get_connection()
    cur  = conn.cursor()
    try:
        cur.execute("SELECT COUNT(*) FROM vehicle_trips WHERE trip_date=%s AND slip_type=%s",
                    (TRIP_DATE, SLIP_TYPE))
        existing = cur.fetchone()[0]
        if existing > 0:
            if overwrite:
                cur.execute("DELETE FROM vehicle_trips WHERE trip_date=%s AND slip_type=%s",
                            (TRIP_DATE, SLIP_TYPE))
                print(f"\n  Cleared {existing} existing records for {TRIP_DATE}")
            else:
                print(f"\n  Data for {TRIP_DATE} already exists ({existing} records). Use --overwrite to replace.")
                return

        cur.execute("SELECT MAX(s_no) FROM vehicle_trips WHERE trip_date=%s AND slip_type=%s",
                    (TRIP_DATE, SLIP_TYPE))
        s_no = (cur.fetchone()[0] or 0) + 1

        inserted = errors = 0
        for rec in records:
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
