import re

def clean_text(text):
    if not text:
        return ""
    text = re.sub(r'[^a-zA-Z0-9\s]', '', text)
    return ' '.join(text.split())

def validate_vehicle_number(vehicle_no):
    if not vehicle_no:
        return False
    v_clean = vehicle_no.replace(" ", "").upper()
    pattern = r'^[A-Z]{2}\d{1,2}[A-Z]{0,3}\d{1,4}$'
    if re.match(pattern, v_clean):
        return True
    return False

def format_vehicle_number(vehicle_no):
    if not vehicle_no:
        return ""
    v_clean = vehicle_no.replace(" ", "").upper()
    match = re.match(r'^([A-Z]{2})(\d{1,2})([A-Z]{0,3})(\d{1,4})$', v_clean)
    if match:
        parts = [p for p in match.groups() if p]
        return " ".join(parts)
    return vehicle_no.upper()
