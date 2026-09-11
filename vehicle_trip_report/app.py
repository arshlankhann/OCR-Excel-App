import streamlit as st  
import os
import sys
from datetime import datetime
import pandas as pd

# Ensure the current directory is in the Python path for imports to work
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import UNIT_AGENCIES, OUTPUT_UNIT_AGENCIES, DEFAULT_REPORTED_BY, DEFAULT_REPORT_PREFIX
from database.db import init_db
from database.models import insert_trip_record, check_rst_exists, get_records_by_date, search_records, get_records_by_month, update_trip_record, delete_trip_record
from utils.image_utils import save_uploaded_image
from utils.validation import validate_vehicle_number, format_vehicle_number
from excel.report import generate_daily_report, get_report_path, generate_monthly_summary

# --- Initialization ---
init_db()

# --- Page Config ---
st.set_page_config(
    page_title="Municipal Corporation Faridabad - Vehicle Trip Report",
    page_icon="🚛",
    layout="wide"
)

# --- Title ---
st.title("Municipal Corporation Faridabad - Vehicle Trip Report")
st.markdown("---")

# --- Session State ---
if 'processed_slips' not in st.session_state:
    st.session_state.processed_slips = []

if 'current_date' not in st.session_state:
    st.session_state.current_date = datetime.now().strftime("%d-%m-%Y")

if 'current_unit' not in st.session_state:
    st.session_state.current_unit = "Pratapgarh"
    
if 'current_reporter' not in st.session_state:
    st.session_state.current_reporter = DEFAULT_REPORTED_BY[0]
    
if 'current_agency' not in st.session_state:
    st.session_state.current_agency = "Auto-detect from Slip"

if 'edit_daily' not in st.session_state:
    st.session_state.edit_daily = False
    
if 'edit_monthly' not in st.session_state:
    st.session_state.edit_monthly = False

if 'current_slip_type' not in st.session_state:
    st.session_state.current_slip_type = "Input"

# --- Sidebar ---
st.sidebar.header("Navigation")
menu = st.sidebar.radio("Go To", ["Upload & OCR", "Search Database", "Excel Reports"])

# --- Function to trigger OCR (lazy import for speed) ---
@st.cache_resource
def load_ocr_engine():
    # Only imports and loads paddleocr when needed
    from paddleocr import PaddleOCR
    return PaddleOCR(use_angle_cls=False, lang='en')

# --- Section 1: Upload & OCR ---
if menu == "Upload & OCR":
    st.header("1. Upload Bulk Slips")
    
    st.radio("Select Slip Type", ["Input", "Output"], key="current_slip_type", horizontal=True)
    
    col_date, col_unit, col_agency, col_reporter = st.columns(4)
    
    with col_date:
        selected_date = st.date_input("Trip Date (Batch)", datetime.strptime(st.session_state.current_date, "%d-%m-%Y"))
        st.session_state.current_date = selected_date.strftime("%d-%m-%Y")
        
    with col_unit:
        if st.session_state.current_slip_type == "Output":
            units_list = ["Pratapgarh", "Mujeri"]
        else:
            units_list = ["Pratapgarh", "Mujeri", "Gurgaon Paper Mills"]
        selected_unit = st.selectbox("Select Processing Unit", units_list, index=units_list.index(st.session_state.current_unit) if st.session_state.current_unit in units_list else 0)
        st.session_state.current_unit = selected_unit
        
    with col_agency:
        current_unit_agencies = []
        agencies_source = OUTPUT_UNIT_AGENCIES if st.session_state.current_slip_type == "Output" else UNIT_AGENCIES
        for ags in agencies_source.values():
            for a in ags:
                if a not in current_unit_agencies:
                    current_unit_agencies.append(a)
        if not current_unit_agencies: current_unit_agencies = ["Other"]
        batch_agencies = ["Auto-detect from Slip"] + [a for a in current_unit_agencies if a != "Other"]
        selected_agency = st.selectbox("Agency Name (Batch)", batch_agencies, index=0 if st.session_state.current_agency not in batch_agencies else batch_agencies.index(st.session_state.current_agency))
        st.session_state.current_agency = selected_agency
        
    with col_reporter:
        # We exclude "Other" from bulk selection to keep it simple, or they can use it
        batch_reporters = [r for r in DEFAULT_REPORTED_BY if r != "Other"]
        selected_reporter = st.selectbox("Reported By (Batch)", batch_reporters, index=0 if st.session_state.current_reporter not in batch_reporters else batch_reporters.index(st.session_state.current_reporter))
        st.session_state.current_reporter = selected_reporter
        
    st.markdown("---")
    uploaded_files = st.file_uploader("Upload slip images (JPG, PNG)", type=["jpg", "jpeg", "png"], accept_multiple_files=True)
        
    if st.button("Process Images"):
        images_to_process = []
        if uploaded_files:
            images_to_process.extend(uploaded_files)
            
        if not images_to_process:
            st.warning("Please upload at least one image.")
        else:
            ocr_engine = load_ocr_engine()
            from ocr.engine import process_slip
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for i, img_file in enumerate(images_to_process):
                status_text.text(f"Processing image {i+1} of {len(images_to_process)}...")
                
                # Save image
                saved_path = save_uploaded_image(img_file)
                
                # Run OCR
                ocr_result = process_slip(saved_path, ocr_engine)
                
                if "error" in ocr_result:
                    st.error(f"Error processing {img_file.name}: {ocr_result['error']}")
                else:
                    # Store in session state for verification
                    st.session_state.processed_slips.append({
                        "id": f"slip_{datetime.now().timestamp()}_{i}",
                        "image_path": saved_path,
                        "rst_no": ocr_result.get("rst_no", ""),
                        "vehicle_no": ocr_result.get("vehicle_no", ""),
                        "net_weight": ocr_result.get("net_weight", ""),
                        "agency_name": ocr_result.get("agency_name", ""),
                        "saved": False
                    })
                    
                progress_bar.progress((i + 1) / len(images_to_process))
                
            status_text.text("Processing complete!")
            st.success(f"Processed {len(images_to_process)} images. Please verify below.")

    st.markdown("---")
    st.header("2. Verification & Saving")
    
    # Process un-saved slips
    unsaved_slips = [s for s in st.session_state.processed_slips if not s['saved']]
    
    if not unsaved_slips:
        st.info("No new slips to verify.")
    else:
        # Check if we have fully valid slips for bulk save
        valid_slips = []
        duplicate_slips = []
        for s in unsaved_slips:
            if s['rst_no'] and check_rst_exists(s['rst_no'], st.session_state.current_unit):
                duplicate_slips.append(s)
            elif s['rst_no'] and s['vehicle_no'] and s['net_weight']:
                valid_slips.append(s)
                
        if duplicate_slips:
            st.error(f"🚨 {len(duplicate_slips)} out of {len(unsaved_slips)} slips are DUPLICATES (RST No. already exists) and cannot be bulk saved.")
            
        # Display the bulk save button right above the individual items
        if valid_slips:
            st.success(f"✅ {len(valid_slips)} out of {len(unsaved_slips)} slips have all required data and are ready to bulk save.")
            if st.button(f"Bulk Save {len(valid_slips)} Valid Slips", type="primary"):
                success_count = 0
                for slip in valid_slips:
                    if not check_rst_exists(slip['rst_no'], st.session_state.current_unit):
                        final_agency = st.session_state.current_agency
                        if final_agency == "Auto-detect from Slip":
                            unit_agencies = []
                            for ags in UNIT_AGENCIES.values():
                                for a in ags:
                                    if a not in unit_agencies and a != "Other":
                                        unit_agencies.append(a)
                            if not unit_agencies: unit_agencies = ["Other"]
                            fallback_agency = unit_agencies[0] if unit_agencies else "Other"
                            final_agency = slip.get('agency_name') or fallback_agency
                            
                        success, _ = insert_trip_record(
                            rst_no=slip['rst_no'],
                            vehicle_no=format_vehicle_number(slip['vehicle_no']),
                            net_weight=slip['net_weight'],
                            agency_name=final_agency,
                            reported_by=st.session_state.current_reporter,
                            image_path=slip['image_path'],
                            processing_unit=st.session_state.current_unit,
                            trip_date=datetime.strptime(st.session_state.current_date, "%d-%m-%Y").strftime("%d-%m-%Y"),
                            slip_type=st.session_state.current_slip_type
                        )
                        if success:
                            slip['saved'] = True
                            success_count += 1
                if success_count > 0:
                    st.success(f"Successfully bulk saved {success_count} records to the database!")
                    st.rerun()

        st.markdown("---")
        st.write("Or review and save individually below:")
        
        for i, slip in enumerate(unsaved_slips):
            with st.expander(f"Slip {i+1} Verification", expanded=True):
                col_img, col_form = st.columns([1, 2])
                
                with col_img:
                    from PIL import Image
                    display_img = Image.open(slip['image_path'])
                    st.image(display_img, use_column_width=True)
                    if st.button("↻ Rotate Image", key=f"rot_{slip['id']}"):
                        display_img = display_img.rotate(-90, expand=True)
                        display_img.save(slip['image_path'])
                        st.rerun()
                    
                with col_form:
                    with st.form(key=f"form_{slip['id']}"):
                        # Warning if fields are missing
                        if not slip['rst_no'] or not slip['vehicle_no'] or not slip['net_weight']:
                            st.warning("Some fields could not be extracted automatically. Please enter them manually.")
                            
                        # Form fields
                        rst_no = st.text_input("RST No (Slip No.) *", value=slip['rst_no'])
                        if rst_no and check_rst_exists(rst_no, st.session_state.current_unit):
                            st.error(f"🚨 Duplicate Alert: RST No. '{rst_no}' already exists for this processing unit! Please discard this slip or correct the number.")
                            
                        vehicle_no = st.text_input("Vehicle Number *", value=slip['vehicle_no'])
                        
                        # Validate vehicle number display
                        if vehicle_no and not validate_vehicle_number(vehicle_no):
                            st.warning(f"Vehicle number '{vehicle_no}' might not be in standard Indian format. Please double check.")
                            
                        net_weight = st.text_input("Net Weight (kg) *", value=slip['net_weight'])
                        
                        # Options with ability to enter new
                        unit_agencies = []
                        agencies_source = OUTPUT_UNIT_AGENCIES if st.session_state.current_slip_type == "Output" else UNIT_AGENCIES
                        for ags in agencies_source.values():
                            for a in ags:
                                if a not in unit_agencies:
                                    unit_agencies.append(a)
                        if not unit_agencies: unit_agencies = ["Other"]
                        default_agency = slip.get('agency_name')
                        if st.session_state.current_agency != "Auto-detect from Slip":
                            default_agency = st.session_state.current_agency
                            
                        if not default_agency or default_agency not in unit_agencies:
                            default_agency = unit_agencies[0] if unit_agencies else "Other"
                            
                        agency_options = unit_agencies if "Other" in unit_agencies else unit_agencies + ["Other"]
                        try:
                            agency_index = agency_options.index(default_agency)
                        except ValueError:
                            agency_index = 0
                            
                        agency = st.selectbox("Agency Name", agency_options, index=agency_index)
                        if agency == "Other":
                            new_agency = st.text_input("Enter New Agency Name", key=f"new_agency_{slip['id']}")
                            agency = new_agency if new_agency.strip() else "Other"
                        reporter_options = DEFAULT_REPORTED_BY + ["Other"]
                        reporter_idx = reporter_options.index(st.session_state.current_reporter) if st.session_state.current_reporter in reporter_options else 0
                        reported_by = st.selectbox("Reported By", reporter_options, index=reporter_idx)
                        if reported_by == "Other":
                            new_reporter = st.text_input("Enter New Reporter Name", key=f"new_reporter_{slip['id']}")
                            reported_by = new_reporter if new_reporter.strip() else "Other"
                            
                        trip_date = st.date_input("Trip Date", datetime.strptime(st.session_state.current_date, "%d-%m-%Y"))
                        
                        col_btn1, col_btn2 = st.columns(2)
                        with col_btn1:
                            save_btn = st.form_submit_button("Save Record")
                        with col_btn2:
                            clear_btn = st.form_submit_button("Discard")
                            
                        if save_btn:
                            if not rst_no or not vehicle_no or not net_weight:
                                st.error("RST No, Vehicle No, and Net Weight are required.")
                            elif check_rst_exists(rst_no, st.session_state.current_unit):
                                st.error(f"RST No. {rst_no} already exists for this processing unit. Please check for duplicates.")
                            else:
                                formatted_vehicle = format_vehicle_number(vehicle_no)
                                formatted_date = trip_date.strftime("%d-%m-%Y")
                                
                                success, msg = insert_trip_record(
                                    rst_no=rst_no,
                                    vehicle_no=formatted_vehicle,
                                    net_weight=net_weight,
                                    agency_name=agency,
                                    reported_by=reported_by,
                                    image_path=slip['image_path'],
                                    processing_unit=st.session_state.current_unit,
                                    trip_date=formatted_date,
                                    slip_type=st.session_state.current_slip_type
                                )
                                
                                if success:
                                    st.success(f"Record {rst_no} saved successfully!")
                                    # Update state
                                    for s in st.session_state.processed_slips:
                                        if s['id'] == slip['id']:
                                            s['saved'] = True
                                    st.rerun()
                                else:
                                    st.error(f"Database error: {msg}")
                                    
                        if clear_btn:
                            for s in st.session_state.processed_slips:
                                if s['id'] == slip['id']:
                                    s['saved'] = True # Mark as saved to dismiss it
                            st.rerun()

# --- Section 2: Search Database ---
elif menu == "Search Database":
    st.header("Search Local Database")
    
    query = st.text_input("Search by RST No, Vehicle No, Date, or Agency")
    if query:
        results = search_records(query)
        if results:
            df = pd.DataFrame(results)
            # Hide some internal columns for display
            display_df = df[['s_no', 'rst_no', 'vehicle_no', 'net_weight', 'agency_name', 'reported_by', 'trip_date', 'trip_time', 'slip_type']]
            st.dataframe(display_df, use_container_width=True)
            
            st.markdown("### Delete Record")
            record_options = {r['id']: f"S.No {r['s_no']} - Slip No. {r['rst_no']} ({r['trip_date']})" for r in results}
            selected_del_id = st.selectbox("Select Record to Delete", options=list(record_options.keys()), format_func=lambda x: record_options[x], key="del_search")
            if st.button("🗑️ Delete Selected Record", type="primary"):
                success, msg = delete_trip_record(selected_del_id)
                if success:
                    st.success("Record deleted successfully! Please search again.")
                    st.rerun()
                else:
                    st.error(f"Failed to delete: {msg}")
        else:
            st.info("No records found.")

# --- Section 3: Excel Reports ---
elif menu == "Excel Reports":
    st.header("Excel Report Generation")
    
    report_type = st.radio("Select Report Type", ["Daily Report", "Monthly Summary"])
    report_slip_type = st.radio("Select Slip Type for Report", ["Input", "Output"], horizontal=True)
    
    if report_type == "Daily Report":
        report_date = st.date_input("Select Date for Report", datetime.now())
        formatted_date = report_date.strftime("%d-%m-%Y")
        report_name = f"{report_slip_type}_{DEFAULT_REPORT_PREFIX}{formatted_date}.xlsx"
        report_path = get_report_path(report_name)
        
        st.write(f"**Target File:** `{report_name}`")
        
        records = get_records_by_date(formatted_date, slip_type=report_slip_type)
        
        if not records:
            st.warning(f"No records found in database for date: {formatted_date}")
        else:
            st.success(f"Found {len(records)} records for {formatted_date}.")
            
            # Display summary table
            df = pd.DataFrame(records)
            if 'rst_no' in df.columns:
                df['rst_no_num'] = pd.to_numeric(df['rst_no'], errors='coerce')
                df = df.sort_values(by=['rst_no_num', 'rst_no'], ascending=[True, True])
                
            display_df = df[['s_no', 'rst_no', 'vehicle_no', 'net_weight', 'agency_name', 'reported_by']]
            st.dataframe(display_df, use_container_width=True)
            
            if not st.session_state.edit_daily:
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("✏️ Edit Record", key="btn_edit_daily"):
                        st.session_state.edit_daily = True
                        st.rerun()
                with col2:
                    if st.button("📊 Generate / Update Excel Report"):
                        with st.spinner("Generating beautiful Excel file with multiple sheets..."):
                            try:
                                generated_path = generate_daily_report(formatted_date, records, slip_type=report_slip_type)
                                st.success("Report generated successfully!")
                                
                                with open(generated_path, "rb") as f:
                                    st.download_button(
                                        label="Download Excel File",
                                        data=f,
                                        file_name=report_name,
                                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                                    )
                            except Exception as e:
                                st.error(f"Failed to generate report: {e}")
            else:
                st.markdown("### Edit Record")
                record_options = {r['id']: f"S.No {r['s_no']} - Slip No. {r['rst_no']}" for r in records}
                selected_record_id = st.selectbox("Select Record to Edit", options=list(record_options.keys()), format_func=lambda x: record_options[x], key="sel_daily")
                
                selected_record = next(r for r in records if r['id'] == selected_record_id)
                
                with st.form("edit_record_form_daily"):
                    rst_no = st.text_input("RST No", value=selected_record['rst_no'])
                    vehicle_no = st.text_input("Vehicle No", value=selected_record['vehicle_no'])
                    net_weight = st.text_input("Net Weight", value=selected_record['net_weight'])
                    
                    unit_agencies = []
                    agencies_source = OUTPUT_UNIT_AGENCIES if report_slip_type == "Output" else UNIT_AGENCIES
                    for ags in agencies_source.values():
                        for a in ags:
                            if a not in unit_agencies and a != "Other" and a != "Custom":
                                unit_agencies.append(a)
                    agency_options = unit_agencies + ["Custom"]
                    default_agency = selected_record['agency_name']
                    if default_agency not in agency_options:
                        agency_options.insert(0, default_agency)
                        
                    agency = st.selectbox("Agency Name", agency_options, index=agency_options.index(default_agency) if default_agency in agency_options else 0)
                    if agency == "Custom":
                        agency = st.text_input("Enter Custom Agency Name")
                        
                    reporter_options = [r for r in DEFAULT_REPORTED_BY if r != "Other" and r != "Custom"] + ["Custom"]
                    default_reporter = selected_record['reported_by']
                    if default_reporter not in reporter_options:
                        reporter_options.insert(0, default_reporter)
                    reported_by = st.selectbox("Reported By", reporter_options, index=reporter_options.index(default_reporter) if default_reporter in reporter_options else 0)
                    if reported_by == "Custom":
                        reported_by = st.text_input("Enter Custom Reporter Name")
                        
                    col_b1, col_b2, col_b3 = st.columns(3)
                    with col_b1:
                        save_btn = st.form_submit_button("💾 Save Data Changes")
                    with col_b2:
                        discard_btn = st.form_submit_button("❌ Discard")
                    with col_b3:
                        delete_btn = st.form_submit_button("🗑️ Delete Record")
                        
                    if save_btn:
                        success, msg = update_trip_record(
                            record_id=selected_record_id,
                            rst_no=rst_no,
                            vehicle_no=vehicle_no,
                            net_weight=net_weight,
                            agency_name=agency,
                            reported_by=reported_by
                        )
                        if success:
                            st.success("Record updated successfully!")
                            st.session_state.edit_daily = False
                            st.rerun()
                        else:
                            st.error(f"Failed to update: {msg}")
                    if discard_btn:
                        st.session_state.edit_daily = False
                        st.rerun()
                    if delete_btn:
                        success, msg = delete_trip_record(selected_record_id)
                        if success:
                            st.success("Record deleted successfully!")
                            st.session_state.edit_daily = False
                            st.rerun()
                        else:
                            st.error(f"Failed to delete: {msg}")

    elif report_type == "Monthly Summary":
        import calendar
        
        col1, col2 = st.columns(2)
        with col1:
            month = st.selectbox("Select Month", range(1, 13), index=datetime.now().month - 1, format_func=lambda x: calendar.month_name[x])
        with col2:
            year = st.selectbox("Select Year", range(2023, datetime.now().year + 2), index=datetime.now().year - 2023)
            
        month_year_str = f"{month:02d}-{year}"
        report_name = f"{report_slip_type}_Monthly_Summary_{month_year_str}.xlsx"
        report_path = get_report_path(report_name)
        
        st.write(f"**Target File:** `{report_name}`")
        
        records = get_records_by_month(month_year_str, slip_type=report_slip_type)
        
        if not records:
            st.warning(f"No records found in database for {calendar.month_name[month]} {year}")
        else:
            st.success(f"Found {len(records)} records for {calendar.month_name[month]} {year}.")
            
            # Display summary table
            df = pd.DataFrame(records)
            if 'rst_no' in df.columns and 'trip_date' in df.columns:
                df['rst_no_num'] = pd.to_numeric(df['rst_no'], errors='coerce')
                df = df.sort_values(by=['trip_date', 'rst_no_num', 'rst_no'], ascending=[True, True, True])
                
            display_df = df[['trip_date', 's_no', 'rst_no', 'vehicle_no', 'net_weight', 'agency_name', 'reported_by']]
            st.dataframe(display_df, use_container_width=True)
            
            if not st.session_state.edit_monthly:
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("✏️ Edit Record", key="btn_edit_monthly"):
                        st.session_state.edit_monthly = True
                        st.rerun()
                with col2:
                    if st.button("📊 Generate / Update Monthly Excel Report"):
                        with st.spinner("Generating beautiful Excel monthly summary..."):
                            try:
                                generated_path = generate_monthly_summary(month_year_str, records, slip_type=report_slip_type)
                                if generated_path:
                                    st.success("Monthly Summary generated successfully!")
                                    
                                    with open(generated_path, "rb") as f:
                                        st.download_button(
                                            label="Download Monthly Excel File",
                                            data=f,
                                            file_name=report_name,
                                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                                        )
                            except Exception as e:
                                st.error(f"Failed to generate report: {e}")
            else:
                st.markdown("### Edit Record")
                record_options = {r['id']: f"S.No {r['s_no']} - Slip No. {r['rst_no']}" for r in records}
                selected_record_id = st.selectbox("Select Record to Edit", options=list(record_options.keys()), format_func=lambda x: record_options[x], key="sel_monthly")
                
                selected_record = next(r for r in records if r['id'] == selected_record_id)
                
                with st.form("edit_record_form_monthly"):
                    rst_no = st.text_input("RST No", value=selected_record['rst_no'])
                    vehicle_no = st.text_input("Vehicle No", value=selected_record['vehicle_no'])
                    net_weight = st.text_input("Net Weight", value=selected_record['net_weight'])
                    
                    unit_agencies = []
                    agencies_source = OUTPUT_UNIT_AGENCIES if report_slip_type == "Output" else UNIT_AGENCIES
                    for ags in agencies_source.values():
                        for a in ags:
                            if a not in unit_agencies and a != "Other" and a != "Custom":
                                unit_agencies.append(a)
                    agency_options = unit_agencies + ["Custom"]
                    default_agency = selected_record['agency_name']
                    if default_agency not in agency_options:
                        agency_options.insert(0, default_agency)
                        
                    agency = st.selectbox("Agency Name", agency_options, index=agency_options.index(default_agency) if default_agency in agency_options else 0)
                    if agency == "Custom":
                        agency = st.text_input("Enter Custom Agency Name")
                        
                    reporter_options = [r for r in DEFAULT_REPORTED_BY if r != "Other" and r != "Custom"] + ["Custom"]
                    default_reporter = selected_record['reported_by']
                    if default_reporter not in reporter_options:
                        reporter_options.insert(0, default_reporter)
                    reported_by = st.selectbox("Reported By", reporter_options, index=reporter_options.index(default_reporter) if default_reporter in reporter_options else 0)
                    if reported_by == "Custom":
                        reported_by = st.text_input("Enter Custom Reporter Name")
                        
                    col_b1, col_b2, col_b3 = st.columns(3)
                    with col_b1:
                        save_btn = st.form_submit_button("💾 Save Data Changes")
                    with col_b2:
                        discard_btn = st.form_submit_button("❌ Discard")
                    with col_b3:
                        delete_btn = st.form_submit_button("🗑️ Delete Record")
                        
                    if save_btn:
                        success, msg = update_trip_record(
                            record_id=selected_record_id,
                            rst_no=rst_no,
                            vehicle_no=vehicle_no,
                            net_weight=net_weight,
                            agency_name=agency,
                            reported_by=reported_by
                        )
                        if success:
                            st.success("Record updated successfully!")
                            st.session_state.edit_monthly = False
                            st.rerun()
                        else:
                            st.error(f"Failed to update: {msg}")
                    if discard_btn:
                        st.session_state.edit_monthly = False
                        st.rerun()
                    if delete_btn:
                        success, msg = delete_trip_record(selected_record_id)
                        if success:
                            st.success("Record deleted successfully!")
                            st.session_state.edit_monthly = False
                            st.rerun()
                        else:
                            st.error(f"Failed to delete: {msg}")
