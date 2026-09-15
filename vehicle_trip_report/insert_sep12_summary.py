"""
Insert Sep 12 Manual Summary Data into vehicle_trips
=====================================================
Data provided:
  SVN       = 179670 kg, 12 trips  → Pratapgarh
  V S Waste = 77460  kg,  6 trips  → Mujeri
  Govt      = 11380  kg,  1 trip   → Mujeri
  Tractor   = 85730  kg, 56 trips  → Mujeri
  J.P Bros  = 111290 kg,  5 trips  → Pratapgarh
  Total     = 4,65,530 kg

Since we don't have individual RST/vehicle numbers, each agency's total
is split evenly across N trips (rounded), with auto-generated RST nos.

Usage:
    python insert_sep12_summary.py              # insert (skip if date exists)
    python insert_sep12_summary.py --overwrite  # delete & re-insert
    python insert_sep12_summary.py --dry-run    # preview only
"""

import os
import sys
import argparse
import math

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from database.db import get_connection

TRIP_DATE   = "12-09-2026"
TRIP_TIME   = "08:00:00"
SLIP_TYPE   = "Input"
REPORTER_PRATAPGARH = "Krishan JE"
REPORTER_MUJERI     = "V S Waste"

# (agency_name, total_weight_kg, num_trips, processing_unit, reported_by)
SEP12_DATA = [
    ("SVN",        179670, 12, "Mujeri",     REPORTER_PRATAPGARH),
    ("V S Waste",   77460,  6, "Mujeri",     REPORTER_MUJERI),
    ("Government",  11380,  1, "Mujeri",     REPORTER_MUJERI),
    ("Tractor",     85730, 56, "Mujeri",     "Tractor"),
    ("J.P Bros",   111290,  5, "Pratapgarh", REPORTER_PRATAPGARH),
]


def build_records():
    """Expand each agency summary into N individual trip records."""
    records = []
    # Use a base RST prefix that won't clash with real RST nos
    rst_counter = 91200  # arbitrary high number for manual entries

    for agency, total_wt, num_trips, unit, reporter in SEP12_DATA:
        base_wt   = total_wt // num_trips
        remainder = total_wt  - base_wt * num_trips

        for i in range(num_trips):
            wt = base_wt + (1 if i == 0 else 0) * remainder  # add remainder to first trip
            rst_no = f"M{rst_counter}"   # "M" prefix marks manual summary entries
            rst_counter += 1

            records.append({
                "rst_no":          rst_no,
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

    return records


def get_next_s_no(cursor):
    cursor.execute(
        "SELECT MAX(s_no) FROM vehicle_trips WHERE trip_date = %s AND slip_type = %s",
        (TRIP_DATE, SLIP_TYPE)
    )
    result = cursor.fetchone()
    return (result[0] or 0) + 1


def delete_sep12(cursor):
    cursor.execute(
        "DELETE FROM vehicle_trips WHERE trip_date = %s AND slip_type = %s",
        (TRIP_DATE, SLIP_TYPE)
    )
    print(f"  Cleared all existing records for {TRIP_DATE}")


def date_has_data(cursor):
    cursor.execute(
        "SELECT COUNT(*) FROM vehicle_trips WHERE trip_date = %s AND slip_type = %s",
        (TRIP_DATE, SLIP_TYPE)
    )
    return cursor.fetchone()[0] > 0


def run(dry_run=False, overwrite=False):
    records = build_records()

    print(f"\n{'DRY RUN — ' if dry_run else ''}Sep 12 Summary Import")
    print("=" * 60)

    # Print preview table
    print(f"\n{'Agency':<15} {'Unit':<12} {'Trips':>6} {'Total Wt (kg)':>14}")
    print("-" * 50)
    for agency, total_wt, num_trips, unit, _ in SEP12_DATA:
        print(f"{agency:<15} {unit:<12} {num_trips:>6} {total_wt:>14,}")
    print("-" * 50)
    grand_total = sum(x[1] for x in SEP12_DATA)
    grand_trips = sum(x[2] for x in SEP12_DATA)
    print(f"{'TOTAL':<15} {'':<12} {grand_trips:>6} {grand_total:>14,}")
    print(f"\nTotal records to insert: {len(records)}")

    if dry_run:
        print("\nDRY RUN complete — nothing inserted.")
        return

    conn = get_connection()
    cursor = conn.cursor()

    try:
        if date_has_data(cursor):
            if overwrite:
                delete_sep12(cursor)
            else:
                print(f"\n  Data for {TRIP_DATE} already exists. Use --overwrite to replace.")
                cursor.close()
                conn.close()
                return

        s_no = get_next_s_no(cursor)
        inserted = 0
        errors   = 0

        for rec in records:
            try:
                cursor.execute("""
                    INSERT INTO vehicle_trips
                        (s_no, rst_no, vehicle_no, net_weight, agency_name, reported_by,
                         trip_date, trip_time, image_path, processing_unit, slip_type)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """, (
                    s_no, rec["rst_no"], rec["vehicle_no"], rec["net_weight"],
                    rec["agency_name"], rec["reported_by"], rec["trip_date"],
                    rec["trip_time"], rec["image_path"], rec["processing_unit"],
                    rec["slip_type"]
                ))
                s_no += 1
                inserted += 1
            except Exception as e:
                errors += 1
                print(f"  ERROR inserting {rec['rst_no']}: {e}")

        conn.commit()
        print(f"\n✅ Done! Inserted: {inserted} | Errors: {errors}")

    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Insert Sep 12 manual summary data")
    parser.add_argument("--dry-run",   action="store_true", help="Preview without inserting")
    parser.add_argument("--overwrite", action="store_true", help="Delete existing Sep 12 records first")
    args = parser.parse_args()
    run(dry_run=args.dry_run, overwrite=args.overwrite)
