import os
import pandas as pd
from openpyxl import Workbook
from openpyxl.drawing.image import Image as OpenpyxlImage
import sys
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import REPORTS_DIR, ROW_HEIGHT, EXCEL_IMAGE_WIDTH, EXCEL_IMAGE_HEIGHT, UNIT_AGENCIES
from excel.formatting import (
    apply_title_formatting, apply_header_formatting, apply_data_row_formatting, 
    set_column_widths, HEADER_FILL_PRATAPGARH, HEADER_FILL_MUJERI, SUMMARY_HEADER_FILL,
    BOLD_FONT, CENTER_ALIGN, LEFT_ALIGN, THIN_BORDER
)
from utils.image_utils import process_image_for_excel

def get_report_path(report_name):
    if not report_name.endswith('.xlsx'):
        report_name += '.xlsx'
    return REPORTS_DIR / report_name

def generate_daily_report(date_str, records, slip_type="Input"):
    """
    date_str: DD-MM-YYYY
    records: list of dicts from db
    """
    dt = datetime.strptime(date_str, "%d-%m-%Y")
    formatted_date_title = dt.strftime("%d/%m/%Y")
    tab_date = dt.strftime("%d-%b")
    
    report_name = f"Vehicle_Trip_Report_{date_str}.xlsx"
    report_path = get_report_path(report_name)
    
    wb = Workbook()
    
    default_sheet = wb.active
    
    df = pd.DataFrame(records)
    if df.empty:
        return None
        
    # Sort by RST No in ascending order
    if 'rst_no' in df.columns:
        df['rst_no_num'] = pd.to_numeric(df['rst_no'], errors='coerce')
        df = df.sort_values(by=['rst_no_num', 'rst_no'], ascending=[True, True])
        
    if 'processing_unit' not in df.columns:
        df['processing_unit'] = 'Pratapgarh'
    df['processing_unit'] = df['processing_unit'].fillna('Pratapgarh')
    
    # Fix missing or 'Other' agency names from older records
    df.loc[(df['processing_unit'] == 'Mujeri') & ((df['agency_name'].isnull()) | (df['agency_name'] == '') | (df['agency_name'] == 'Other')), 'agency_name'] = 'V S Waste'
    df.loc[(df['processing_unit'] == 'Pratapgarh') & ((df['agency_name'].isnull()) | (df['agency_name'] == '')), 'agency_name'] = 'SVN'
        
    units = df['processing_unit'].unique()
    
    for unit in ['Pratapgarh', 'Mujeri', 'Gurgaon Paper Mills']:
        if unit not in units:
            continue
            
        unit_df = df[df['processing_unit'] == unit].copy()
        
        # Ensure net_weight is numeric for summing and excel formatting
        unit_df['net_weight'] = pd.to_numeric(unit_df['net_weight'], errors='coerce').fillna(0)
        
        # 1. Data Sheet
        data_sheet = wb.create_sheet(f"{unit} {tab_date}")
        
        title = f"Municipal Corporation Faridabad - {unit} Processing Unit - {slip_type} Vehicle Trip Report ({formatted_date_title})"
        data_sheet.append([title])
        data_sheet.append([])
        
        headers = ["S.No", "RST No (Slip No.)", "Vehicle Number", "Net Weight (kg)", "Agency Name", "Reported By", "Slip Image"]
        widths = [8, 18, 20, 18, 20, 20, 45]
        
        if unit == "Pratapgarh":
            header_fill = HEADER_FILL_PRATAPGARH
        elif unit == "Mujeri":
            header_fill = HEADER_FILL_MUJERI
        else:
            from excel.formatting import HEADER_FILL_GURGAON
            header_fill = HEADER_FILL_GURGAON
            
        data_sheet.append(headers)
        
        apply_title_formatting(data_sheet, len(headers))
        apply_header_formatting(data_sheet, 3, header_fill)
        set_column_widths(data_sheet, headers, widths)
        
        next_row = 4
        s_no = 1
        for _, record in unit_df.iterrows():
            row_data = [
                s_no,
                record.get('rst_no', ''),
                record.get('vehicle_no', ''),
                record.get('net_weight', '')
            ]
            
            row_data.append(record.get('agency_name', ''))
            row_data.append(record.get('reported_by', ''))
            row_data.append("") # Placeholder for image
            
            data_sheet.append(row_data)
            
            # Embed Image
            image_path = record.get('image_path')
            if image_path and os.path.exists(image_path):
                temp_img_path = process_image_for_excel(image_path)
                if temp_img_path:
                    img = OpenpyxlImage(temp_img_path)
                    img_col_letter = 'G'
                    img.anchor = f"{img_col_letter}{next_row}"
                    data_sheet.add_image(img)
                    data_sheet.row_dimensions[next_row].height = ROW_HEIGHT
            else:
                img_col_idx = 7
                data_sheet.cell(row=next_row, column=img_col_idx, value="No Image")
                
            apply_data_row_formatting(data_sheet, next_row)
            next_row += 1
            s_no += 1
            
        # Add Total Row
        total_weight = unit_df['net_weight'].sum()
        total_row = [""] * len(headers)
        total_row[2] = "Total Net Weight (kg)"
        total_row[3] = total_weight
        
        data_sheet.append(total_row)
        for col_idx in range(1, len(headers) + 1):
            cell = data_sheet.cell(row=next_row, column=col_idx)
            cell.font = BOLD_FONT
            cell.alignment = CENTER_ALIGN
            cell.border = THIN_BORDER
            
        next_row += 1
            
        # 2. Summary Sheet
        summary_sheet = wb.create_sheet(f"{unit} Summary")
        
        summary_sheet.append([f"Summary - {unit} Processing Unit {slip_type} Vehicle Trip Report ({formatted_date_title})"])
        summary_sheet['A1'].font = BOLD_FONT
        summary_sheet.append([])
        
        current_row = 3
        
        # Table 1: Overall Statistics
        summary_sheet.cell(row=current_row, column=1, value="Overall Statistics").font = BOLD_FONT
        current_row += 1
        
        total_trips = len(unit_df)
        total_weight = unit_df['net_weight'].sum()
        avg_weight = total_weight / total_trips if total_trips > 0 else 0
        
        stats = [
            ["Total Trips", total_trips],
            ["Total Net Weight (kg)", total_weight],
            ["Average Net Weight per Trip", round(avg_weight, 5)]
        ]
        
        for row_data in stats:
            summary_sheet.append(row_data)
            apply_data_row_formatting(summary_sheet, current_row)
            summary_sheet.cell(row=current_row, column=1).alignment = LEFT_ALIGN
            current_row += 1
            
        current_row += 2
        
        # Table 2: Agency-wise Breakdown
        summary_sheet.cell(row=current_row, column=1, value="Agency-wise Breakdown").font = BOLD_FONT
        current_row += 1
        
        headers = ["Agency Name", "No. of Trips", "Total Net Weight (kg)", "% of Total Weight"]
        summary_sheet.append(headers)
        apply_header_formatting(summary_sheet, current_row, SUMMARY_HEADER_FILL)
        current_row += 1
        
        agency_grouped = unit_df.groupby('agency_name').agg(
            trips=('rst_no', 'count'),
            weight=('net_weight', 'sum')
        ).reset_index()
        
        for _, row in agency_grouped.iterrows():
            pct = row['weight'] / total_weight if total_weight > 0 else 0
            summary_sheet.append([row['agency_name'], row['trips'], row['weight'], pct])
            apply_data_row_formatting(summary_sheet, current_row)
            summary_sheet.cell(row=current_row, column=1).alignment = LEFT_ALIGN
            current_row += 1
            
        summary_sheet.append(["Total", total_trips, total_weight, 1])
        apply_data_row_formatting(summary_sheet, current_row)
        for col in range(1, 5):
            summary_sheet.cell(row=current_row, column=col).font = BOLD_FONT
        summary_sheet.cell(row=current_row, column=1).alignment = LEFT_ALIGN
        current_row += 2
            
        # Table 3: Reported By - Breakdown
        summary_sheet.cell(row=current_row, column=1, value="Reported By - Breakdown").font = BOLD_FONT
        current_row += 1
        
        headers = ["Reported By", "No. of Trips", "Total Net Weight (kg)"]
        summary_sheet.append(headers)
        apply_header_formatting(summary_sheet, current_row, SUMMARY_HEADER_FILL)
        current_row += 1
        
        reporter_grouped = unit_df.groupby('reported_by').agg(
            trips=('rst_no', 'count'),
            weight=('net_weight', 'sum')
        ).reset_index()
        
        for _, row in reporter_grouped.iterrows():
            summary_sheet.append([row['reported_by'], row['trips'], row['weight']])
            apply_data_row_formatting(summary_sheet, current_row)
            summary_sheet.cell(row=current_row, column=1).alignment = LEFT_ALIGN
            current_row += 1
            
        current_row += 2
        
        # Table 4: Vehicle-wise Trip Count
        summary_sheet.cell(row=current_row, column=1, value="Vehicle-wise Trip Count (Repeat Vehicles)").font = BOLD_FONT
        current_row += 1
        
        headers = ["Vehicle Number", "No. of Trips", "Total Net Weight (kg)"]
        summary_sheet.append(headers)
        apply_header_formatting(summary_sheet, current_row, SUMMARY_HEADER_FILL)
        current_row += 1
        
        vehicle_grouped = unit_df.groupby('vehicle_no').agg(
            trips=('rst_no', 'count'),
            weight=('net_weight', 'sum')
        ).reset_index().sort_values('trips', ascending=False)
        
        for _, row in vehicle_grouped.iterrows():
            summary_sheet.append([row['vehicle_no'], row['trips'], row['weight']])
            apply_data_row_formatting(summary_sheet, current_row)
            summary_sheet.cell(row=current_row, column=1).alignment = LEFT_ALIGN
            current_row += 1
            
        set_column_widths(summary_sheet, ["A", "B", "C", "D"], [35, 15, 25, 20])

    if len(wb.sheetnames) > 1 and default_sheet.title in wb.sheetnames:
        wb.remove(default_sheet)
        
    wb.save(report_path)
    return str(report_path)

def generate_monthly_summary(month_year_str, records, slip_type="Input"):
    """
    month_year_str: MM-YYYY
    records: list of dicts from db
    """
    report_name = f"Monthly_Summary_{month_year_str}.xlsx"
    report_path = get_report_path(report_name)
    
    wb = Workbook()
    default_sheet = wb.active
    
    df = pd.DataFrame(records)
    if df.empty:
        return None
        
    if 'processing_unit' not in df.columns:
        df['processing_unit'] = 'Pratapgarh'
    df['processing_unit'] = df['processing_unit'].fillna('Pratapgarh')
    
    # Fix missing or 'Other' agency names from older records
    df.loc[(df['processing_unit'] == 'Mujeri') & ((df['agency_name'].isnull()) | (df['agency_name'] == '') | (df['agency_name'] == 'Other')), 'agency_name'] = 'V S Waste'
    df.loc[(df['processing_unit'] == 'Pratapgarh') & ((df['agency_name'].isnull()) | (df['agency_name'] == '')), 'agency_name'] = 'SVN'
    df['net_weight'] = pd.to_numeric(df['net_weight'], errors='coerce').fillna(0)
    
    # Extract day from trip_date (DD-MM-YYYY)
    df['day'] = df['trip_date'].apply(lambda x: x.split('-')[0] if isinstance(x, str) else '')
    
    # --- 1. Overall Summary (All Units) ---
    overall_sheet = wb.create_sheet("Overall Summary")
    title = f"Municipal Corporation Faridabad - Overall {slip_type} Monthly Summary ({month_year_str})"
    overall_sheet.append([title])
    overall_sheet['A1'].font = BOLD_FONT
    overall_sheet.append([])
    
    pivot_all = pd.pivot_table(df, values='net_weight', index='day', columns='agency_name', aggfunc='sum', fill_value=0)
    
    if 'Other' in pivot_all.columns:
        pivot_all = pivot_all.drop(columns=['Other'])
        
    pivot_all['Total Weight (kg)'] = pivot_all.sum(axis=1)
    pivot_all.loc['Total'] = pivot_all.sum()
    
    # Reorder columns by processing unit
    ordered_agencies = []
    unit_headers = ["Day (Date)"]
    agency_headers = [" "]
    
    for unit_name, agencies in UNIT_AGENCIES.items():
        # Agencies present in this month's data
        unit_agencies_in_data = [a for a in agencies if a in pivot_all.columns and a != "Total Weight (kg)" and a not in ordered_agencies]
        if unit_agencies_in_data:
            ordered_agencies.extend(unit_agencies_in_data)
            unit_headers.extend([unit_name] + [" "] * (len(unit_agencies_in_data) - 1))
            agency_headers.extend(unit_agencies_in_data)
            
    # Add any leftovers that might not be mapped
    leftovers = [a for a in pivot_all.columns if a not in ordered_agencies and a != "Total Weight (kg)"]
    if leftovers:
        ordered_agencies.extend(leftovers)
        unit_headers.extend(["Other"] + [" "] * (len(leftovers) - 1))
        agency_headers.extend(leftovers)
        
    ordered_agencies.append("Total Weight (kg)")
    unit_headers.append("Total Weight (kg)")
    agency_headers.append(" ")
    
    # Reorder pivot_all columns
    pivot_all = pivot_all[ordered_agencies]
    
    overall_sheet.append(unit_headers)
    overall_sheet.append(agency_headers)
    

    from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
    # Style FIRST to ensure every cell has the formatting applied to it properly
    for row in overall_sheet.iter_rows(min_row=3, max_row=4, min_col=1, max_col=len(unit_headers)):
        for cell in row:
            if cell.value is None or cell.value == "":
                cell.value = " "
            cell.font = Font(name="Arial", size=11, bold=True, color="FFFFFFFF")
            cell.fill = PatternFill(start_color="FF366092", end_color="FF366092", fill_type="solid")
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = Border(
                left=Side(style="thin"), right=Side(style="thin"),
                top=Side(style="thin"), bottom=Side(style="thin")
            )

    from openpyxl.utils import get_column_letter
    # Merge cells for unit headers SECOND
    start_col = 2
    for unit_name, agencies in UNIT_AGENCIES.items():
        count = sum(1 for a in agencies if a in pivot_all.columns and a != "Total Weight (kg)")
        if count > 1:
            overall_sheet.merge_cells(start_row=3, start_column=start_col, end_row=3, end_column=start_col + count - 1)
        if count > 0:
            start_col += count
            
    if leftovers and len(leftovers) > 1:
        overall_sheet.merge_cells(start_row=3, start_column=start_col, end_row=3, end_column=start_col + len(leftovers) - 1)
        
    # Merge "Day (Date)" and "Total" vertically
    total_col = len(unit_headers)
    overall_sheet.merge_cells(start_row=3, start_column=1, end_row=4, end_column=1)
    overall_sheet.merge_cells(start_row=3, start_column=total_col, end_row=4, end_column=total_col)
    
    current_row = 5
    for day in pivot_all.index:
        row_data = [day]
        for agency in ordered_agencies:
            row_data.append(pivot_all.loc[day, agency])
        overall_sheet.append(row_data)
        apply_data_row_formatting(overall_sheet, current_row)
        
        if day == 'Total':
            for col in range(1, len(agency_headers) + 1):
                overall_sheet.cell(row=current_row, column=col).font = BOLD_FONT
        current_row += 1
        
    widths = [15] + [20] * len(ordered_agencies)
    for i, width in enumerate(widths):
        col_letter = get_column_letter(i + 1)
        overall_sheet.column_dimensions[col_letter].width = width

    # --- 2. Unit-Specific Summaries ---
    units = df['processing_unit'].unique()
    
    for unit in ['Pratapgarh', 'Mujeri', 'Gurgaon Paper Mills']:
        if unit not in units:
            continue
            
        unit_df = df[df['processing_unit'] == unit].copy()
        sheet = wb.create_sheet(f"{unit[:15]} Summary")
        
        title = f"Municipal Corporation Faridabad - {unit} - {slip_type} Monthly Summary ({month_year_str})"
        sheet.append([title])
        sheet['A1'].font = BOLD_FONT
        sheet.append([])
        
        # Pivot table: Rows = day, Columns = agency, Values = sum(net_weight)
        pivot = pd.pivot_table(unit_df, values='net_weight', index='day', columns='agency_name', aggfunc='sum', fill_value=0)
        
        if 'Other' in pivot.columns:
            pivot = pivot.drop(columns=['Other'])
        
        # Add Total column
        pivot['Total Weight (kg)'] = pivot.sum(axis=1)
        
        # Add Total row
        pivot.loc['Total'] = pivot.sum()
        
        agencies = list(pivot.columns)
        headers = ["Day (Date)"] + agencies
        sheet.append(headers)
        
        if unit == "Pratapgarh":
            header_fill = HEADER_FILL_PRATAPGARH
        elif unit == "Mujeri":
            header_fill = HEADER_FILL_MUJERI
        else:
            from excel.formatting import HEADER_FILL_GURGAON
            header_fill = HEADER_FILL_GURGAON
            
        apply_header_formatting(sheet, 3, header_fill)
        
        current_row = 4
        for day in pivot.index:
            row_data = [day]
            for agency in agencies:
                row_data.append(pivot.loc[day, agency])
            sheet.append(row_data)
            apply_data_row_formatting(sheet, current_row)
            
            # Make Total row bold
            if day == 'Total':
                for col in range(1, len(headers) + 1):
                    sheet.cell(row=current_row, column=col).font = BOLD_FONT
                    
            current_row += 1
            
        # Set column widths
        widths = [15] + [20] * len(agencies)
        for i, width in enumerate(widths):
            col_letter = chr(65 + i) if i < 26 else chr(64 + i // 26) + chr(65 + (i % 26))
            sheet.column_dimensions[col_letter].width = width

    if len(wb.sheetnames) > 1 and default_sheet.title in wb.sheetnames:
        wb.remove(default_sheet)
        
    wb.save(report_path)
    return str(report_path)
