from database.db import get_connection
import sqlite3
from datetime import datetime

def insert_trip_record(rst_no, vehicle_no, net_weight, agency_name, reported_by, image_path, processing_unit, trip_date=None, trip_time=None, slip_type="Input"):
    """Inserts a new trip record into the database."""
    if not trip_date:
        trip_date = datetime.now().strftime("%d-%m-%Y")
    
    if not trip_time:
        trip_time = datetime.now().strftime("%H:%M:%S")

    conn = get_connection()
    cursor = conn.cursor()
    
    # Calculate the next S.No
    cursor.execute("SELECT MAX(s_no) FROM vehicle_trips WHERE trip_date = ?", (trip_date,))
    result = cursor.fetchone()
    next_s_no = (result[0] or 0) + 1

    try:
        cursor.execute('''
            INSERT INTO vehicle_trips 
            (s_no, rst_no, vehicle_no, net_weight, agency_name, reported_by, trip_date, trip_time, image_path, processing_unit, slip_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (next_s_no, str(rst_no), str(vehicle_no), str(net_weight), agency_name, reported_by, trip_date, trip_time, image_path, processing_unit, slip_type))
        conn.commit()
        return True, "Success"
    except sqlite3.IntegrityError:
        return False, f"RST No. {rst_no} already exists for this processing unit."
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()

def check_rst_exists(rst_no, processing_unit, slip_type="Input"):
    """Checks if an RST number already exists in the database for the given processing unit and slip type."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM vehicle_trips WHERE rst_no = ? AND processing_unit = ? AND slip_type = ?", (str(rst_no), processing_unit, slip_type))
    exists = cursor.fetchone() is not None
    conn.close()
    return exists

def get_records_by_date(trip_date, slip_type="Input"):
    """Retrieves all records for a specific date."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM vehicle_trips WHERE trip_date = ? AND slip_type = ? ORDER BY s_no ASC", (trip_date, slip_type))
    records = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return records

def get_records_by_month(month_year_str, slip_type="Input"):
    """Retrieves all records for a specific month and year (format: MM-YYYY)."""
    conn = get_connection()
    cursor = conn.cursor()
    search_pattern = f"%{month_year_str}"
    cursor.execute("SELECT * FROM vehicle_trips WHERE trip_date LIKE ? AND slip_type = ? ORDER BY trip_date ASC, s_no ASC", (search_pattern, slip_type))
    records = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return records

def search_records(query, slip_type=None):
    """Searches records by RST No or Vehicle No."""
    conn = get_connection()
    cursor = conn.cursor()
    search_term = f"%{query}%"
    if slip_type:
        cursor.execute('''
            SELECT * FROM vehicle_trips 
            WHERE (rst_no LIKE ? OR vehicle_no LIKE ? OR trip_date LIKE ? OR agency_name LIKE ?) AND slip_type = ?
            ORDER BY created_at DESC
        ''', (search_term, search_term, search_term, search_term, slip_type))
    else:
        cursor.execute('''
            SELECT * FROM vehicle_trips 
            WHERE rst_no LIKE ? OR vehicle_no LIKE ? OR trip_date LIKE ? OR agency_name LIKE ?
            ORDER BY created_at DESC
        ''', (search_term, search_term, search_term, search_term))
    records = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return records

def update_trip_record(record_id, rst_no, vehicle_no, net_weight, agency_name, reported_by):
    """Updates an existing trip record in the database."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            UPDATE vehicle_trips 
            SET rst_no = ?, vehicle_no = ?, net_weight = ?, agency_name = ?, reported_by = ?
            WHERE id = ?
        ''', (str(rst_no), str(vehicle_no), str(net_weight), agency_name, reported_by, record_id))
        conn.commit()
        return True, "Success"
    except sqlite3.IntegrityError:
        return False, f"RST No. {rst_no} already exists for this processing unit."
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()

def delete_trip_record(record_id):
    """Deletes a trip record from the database."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM vehicle_trips WHERE id = ?", (record_id,))
        conn.commit()
        return True, "Success"
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()

