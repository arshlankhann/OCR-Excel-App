import sys, os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from database.models import get_records_by_month
from excel.report import generate_monthly_summary

records = get_records_by_month("09-2026", slip_type="Input")
print(f"Records found: {len(records)}")
path = generate_monthly_summary("09-2026", records, slip_type="Input")
print(f"Report generated: {path}")
