"""
Bulk Import Script: Vehicle Trip List Excel -> PostgreSQL Database
=================================================================
Reads all day-wise Excel files from the 'Vehical Trip List' folder and
inserts trip records for both Pratapgarh and Mujeri processing units.

Uses direct ZIP/XML parsing to bypass embedded images in large files.

Usage:
    python import_excel_data.py
    python import_excel_data.py --dry-run        # preview without inserting
    python import_excel_data.py --overwrite      # delete & re-insert for a date/unit
"""

import os
import sys
import re
import argparse
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime

# Ensure the project root is on the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from database.db import get_connection

# ─────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────
EXCEL_FOLDER = os.path.join(os.path.dirname(__file__), "Vehical Trip List")

UNIT_CONFIG = {
    "Pratapgarh": {
        "processing_unit": "Pratapgarh",
        # col indices (0-based): s_no=0, rst=1, veh=2, wt=3, agency=4, reported=5
        "col_map": {"s_no": 0, "rst_no": 1, "vehicle_no": 2,
                    "net_weight": 3, "agency_name": 4, "reported_by": 5},
    },
    "Mujeri": {
        "processing_unit": "Mujeri",
        # Mujeri has no Agency column: s_no=0, rst=1, veh=2, wt=3, reported=4
        "col_map": {"s_no": 0, "rst_no": 1, "vehicle_no": 2,
                    "net_weight": 3, "agency_name": None, "reported_by": 4},
    },
}

# Excel XML namespace
NS = {"ss": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}

# ─────────────────────────────────────────────────────────────────────
# Fast XML-based Excel reader (bypasses embedded images)
# ─────────────────────────────────────────────────────────────────────

def get_sheet_names(zf):
    """Return list of (sheet_name, sheet_xml_path) from workbook.xml."""
    wb_xml = zf.read("xl/workbook.xml")
    root = ET.fromstring(wb_xml)
    sheets = []
    for s in root.findall(".//ss:sheet", NS):
        name = s.get("name")
        r_id = s.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
        sheets.append((name, r_id))

    # Read relationships to get actual xml paths
    rels_xml = zf.read("xl/_rels/workbook.xml.rels")
    rels_root = ET.fromstring(rels_xml)
    rid_to_target = {}
    for rel in rels_root.findall(".//{http://schemas.openxmlformats.org/package/2006/relationships}Relationship"):
        rid_to_target[rel.get("Id")] = rel.get("Target")

    result = []
    for name, r_id in sheets:
        target = rid_to_target.get(r_id, "")
        xml_path = f"xl/{target}" if not target.startswith("xl/") else target
        result.append((name, xml_path))
    return result


def get_shared_strings(zf):
    """Load shared strings table (used for string cell values)."""
    if "xl/sharedStrings.xml" not in zf.namelist():
        return []
    xml_data = zf.read("xl/sharedStrings.xml")
    root = ET.fromstring(xml_data)
    strings = []
    for si in root.findall("ss:si", NS):
        # Concatenate all <t> text in this <si>
        text = "".join(t.text or "" for t in si.findall(".//ss:t", NS))
        strings.append(text)
    return strings


def read_sheet_rows(zf, xml_path, shared_strings):
    """
    Parse a sheet XML and yield rows as lists of cell values.
    Much faster than openpyxl for files with embedded images.
    """
    try:
        xml_data = zf.read(xml_path)
    except KeyError:
        return

    root = ET.fromstring(xml_data)
    sheet_data = root.find("ss:sheetData", NS)
    if sheet_data is None:
        return

    for row_elem in sheet_data.findall("ss:row", NS):
        row_idx = int(row_elem.get("r", 0))
        # Build a dict: col_index -> value
        cell_vals = {}
        for cell in row_elem.findall("ss:c", NS):
            ref = cell.get("r", "")
            # Extract column letters from ref like "A1", "BC3"
            col_letters = re.match(r"([A-Z]+)", ref)
            if not col_letters:
                continue
            col_num = col_letters_to_index(col_letters.group(1))

            cell_type = cell.get("t", "")
            v_elem = cell.find("ss:v", NS)
            if v_elem is None or v_elem.text is None:
                cell_vals[col_num] = None
                continue

            raw = v_elem.text
            if cell_type == "s":
                # Shared string
                try:
                    cell_vals[col_num] = shared_strings[int(raw)]
                except IndexError:
                    cell_vals[col_num] = raw
            elif cell_type == "str" or cell_type == "inlineStr":
                cell_vals[col_num] = raw
            else:
                # Numeric — try int first, then float
                try:
                    val = int(raw) if "." not in raw else float(raw)
                    cell_vals[col_num] = val
                except ValueError:
                    cell_vals[col_num] = raw

        if not cell_vals:
            continue

        max_col = max(cell_vals.keys())
        row = [cell_vals.get(i) for i in range(max_col + 1)]
        yield row


def col_letters_to_index(letters):
    """Convert Excel column letters (A, B, ..., Z, AA, ...) to 0-based index."""
    result = 0
    for ch in letters:
        result = result * 26 + (ord(ch) - ord("A") + 1)
    return result - 1


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────

def extract_date_from_title(title_text):
    """Extract DD-MM-YYYY from a title like '... (01/09/2026)'."""
    if not title_text:
        return None
    m = re.search(r"\((\d{2}/\d{2}/\d{4})\)", str(title_text))
    if m:
        day, month, year = m.group(1).split("/")
        return f"{day}-{month}-{year}"
    return None


def get_unit_key_for_sheet(sheet_name):
    """Return 'Pratapgarh', 'Mujeri', or None (for summary sheets)."""
    lower = sheet_name.lower()
    if "summary" in lower:
        return None
    if "pratapgarh" in lower:
        return "Pratapgarh"
    if "mujeri" in lower:
        return "Mujeri"
    return None


def is_data_row(row, col_map):
    """Return True if row looks like a valid trip record."""
    try:
        s_no_idx = col_map["s_no"]
        rst_idx = col_map["rst_no"]
        if len(row) <= max(s_no_idx, rst_idx):
            return False
        s_no = row[s_no_idx]
        rst  = row[rst_idx]
        if s_no is None or rst is None:
            return False
        int(float(str(s_no)))
        str(rst).strip()
        return True
    except (ValueError, TypeError):
        return False


def parse_rows_to_records(rows_iter, unit_key):
    """Convert raw row iterator to list of record dicts."""
    cfg = UNIT_CONFIG[unit_key]
    col = cfg["col_map"]
    trip_date = None
    records = []
    all_rows = list(rows_iter)

    # Row 0 = title with date
    if all_rows:
        first_row = all_rows[0]
        trip_date = extract_date_from_title(first_row[0] if first_row else None)

    # Data starts at row index 3 (4th row)
    for row in all_rows[3:]:
        if not is_data_row(row, col):
            continue

        def get_col(idx):
            if idx is None or idx >= len(row):
                return ""
            v = row[idx]
            return str(v).strip() if v is not None else ""

        s_no_val = row[col["s_no"]]
        try:
            s_no = int(float(str(s_no_val)))
        except (ValueError, TypeError):
            continue

        rst_no     = get_col(col["rst_no"])
        vehicle_no = get_col(col["vehicle_no"])
        net_weight = get_col(col["net_weight"])
        agency     = get_col(col["agency_name"])
        reported   = get_col(col["reported_by"])

        if not rst_no or not vehicle_no:
            continue

        records.append({
            "s_no":            s_no,
            "rst_no":          rst_no,
            "vehicle_no":      vehicle_no,
            "net_weight":      net_weight,
            "agency_name":     agency,
            "reported_by":     reported,
            "trip_date":       trip_date,
            "trip_time":       None,
            "image_path":      None,
            "processing_unit": cfg["processing_unit"],
            "slip_type":       "Input",
        })

    return records


# ─────────────────────────────────────────────────────────────────────
# Database helpers
# ─────────────────────────────────────────────────────────────────────

def rst_exists(cursor, rst_no, processing_unit, slip_type="Input"):
    cursor.execute(
        "SELECT 1 FROM vehicle_trips WHERE rst_no=%s AND processing_unit=%s AND slip_type=%s",
        (rst_no, processing_unit, slip_type)
    )
    return cursor.fetchone() is not None


def delete_records_for_date_unit(cursor, trip_date, processing_unit, slip_type="Input"):
    cursor.execute(
        "DELETE FROM vehicle_trips WHERE trip_date=%s AND processing_unit=%s AND slip_type=%s",
        (trip_date, processing_unit, slip_type)
    )


def insert_record(cursor, rec):
    """Insert one record. Returns (success, message)."""
    try:
        cursor.execute("""
            INSERT INTO vehicle_trips
                (s_no, rst_no, vehicle_no, net_weight, agency_name, reported_by,
                 trip_date, trip_time, image_path, processing_unit, slip_type)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            rec["s_no"], rec["rst_no"], rec["vehicle_no"], rec["net_weight"],
            rec["agency_name"], rec["reported_by"], rec["trip_date"], rec["trip_time"],
            rec["image_path"], rec["processing_unit"], rec["slip_type"]
        ))
        return True, "inserted"
    except Exception as e:
        return False, str(e)


# ─────────────────────────────────────────────────────────────────────
# Main import logic
# ─────────────────────────────────────────────────────────────────────

def run_import(dry_run=False, overwrite=False):
    if not os.path.isdir(EXCEL_FOLDER):
        print(f"ERROR: Excel folder not found: {EXCEL_FOLDER}")
        sys.exit(1)

    excel_files = sorted(f for f in os.listdir(EXCEL_FOLDER) if f.endswith(".xlsx"))
    if not excel_files:
        print("ERROR: No .xlsx files found.")
        sys.exit(1)

    print(f"Found {len(excel_files)} Excel file(s)")
    print(f"Mode: {'DRY RUN' if dry_run else ('OVERWRITE' if overwrite else 'SKIP existing RSTs')}")
    print("=" * 70)

    total_inserted = 0
    total_skipped  = 0
    total_errors   = 0

    conn = None if dry_run else get_connection()

    try:
        for fname in excel_files:
            fpath = os.path.join(EXCEL_FOLDER, fname)
            file_size_mb = os.path.getsize(fpath) / 1024 / 1024
            print(f"\nFILE: {fname}  ({file_size_mb:.1f} MB)")

            try:
                zf = zipfile.ZipFile(fpath, "r")
                shared_strings = get_shared_strings(zf)
                sheet_list = get_sheet_names(zf)
            except Exception as e:
                print(f"  WARNING: Could not open: {e}")
                continue

            for sheet_name, xml_path in sheet_list:
                unit_key = get_unit_key_for_sheet(sheet_name)
                if unit_key is None:
                    continue  # skip summary sheets

                rows_iter = read_sheet_rows(zf, xml_path, shared_strings)
                records = parse_rows_to_records(rows_iter, unit_key)

                if not records:
                    print(f"  [{sheet_name}] -> No data rows, skipping.")
                    continue

                trip_date = records[0]["trip_date"] or "unknown"
                processing_unit = UNIT_CONFIG[unit_key]["processing_unit"]
                print(f"  [{sheet_name}] -> {len(records)} records | Date: {trip_date} | Unit: {processing_unit}")

                if dry_run:
                    for r in records[:2]:
                        print(f"    RST={r['rst_no']}, Veh={r['vehicle_no']}, Wt={r['net_weight']}, "
                              f"Agency='{r['agency_name']}', By={r['reported_by']}")
                    if len(records) > 2:
                        print(f"    ... and {len(records)-2} more")
                    total_inserted += len(records)
                    continue

                cursor = conn.cursor()
                if overwrite:
                    delete_records_for_date_unit(cursor, trip_date, processing_unit)
                    print(f"    Cleared existing records for {trip_date}/{processing_unit}")

                fi = fs = fe = 0
                for rec in records:
                    if not overwrite and rst_exists(cursor, rec["rst_no"], rec["processing_unit"]):
                        fs += 1
                        continue
                    ok, msg = insert_record(cursor, rec)
                    if ok:
                        fi += 1
                    else:
                        fe += 1
                        print(f"    ERROR RST {rec['rst_no']}: {msg}")

                conn.commit()
                cursor.close()
                print(f"    -> Inserted: {fi} | Skipped: {fs} | Errors: {fe}")
                total_inserted += fi
                total_skipped  += fs
                total_errors   += fe

            zf.close()

    finally:
        if conn:
            conn.close()

    print("\n" + "=" * 70)
    if dry_run:
        print(f"DRY RUN complete. Would insert ~{total_inserted} records.")
    else:
        print(f"Import complete!")
        print(f"  Inserted : {total_inserted}")
        print(f"  Skipped  : {total_skipped}")
        print(f"  Errors   : {total_errors}")


# ─────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import Vehicle Trip List Excel data into PostgreSQL")
    parser.add_argument("--dry-run", action="store_true", help="Preview without inserting")
    parser.add_argument("--overwrite", action="store_true",
                        help="Delete existing records for a date/unit before inserting")
    args = parser.parse_args()
    run_import(dry_run=args.dry_run, overwrite=args.overwrite)
