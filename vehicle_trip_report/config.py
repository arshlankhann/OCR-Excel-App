import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Base directories
BASE_DIR = Path(__file__).parent.absolute()
DATA_DIR = BASE_DIR / "data"

IMAGES_DIR = DATA_DIR / "images"
REPORTS_DIR = DATA_DIR / "reports"
DATABASE_DIR = DATA_DIR / "database"
BACKUPS_DIR = DATA_DIR / "backups"

# Ensure directories exist
for directory in [IMAGES_DIR, REPORTS_DIR, DATABASE_DIR, BACKUPS_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# Database configuration
DB_PATH = DATABASE_DIR / "vehicle_trips.db"
DATABASE_URL = os.environ.get("DATABASE_URL")

# Excel configuration
DEFAULT_REPORT_PREFIX = "Vehicle_Trip_Report_"
# The width and height for images embedded in Excel
EXCEL_IMAGE_WIDTH = 400
EXCEL_IMAGE_HEIGHT = 200
ROW_HEIGHT = 160 # Points in Excel, enough to fit 200px height

# Pre-populated dropdown lists (can be extended)
UNIT_AGENCIES = {
    "Pratapgarh": ["SVN", "J.P Bros", "Government", "Other"],
    "Mujeri": ["V S Waste", "Tractor", "Government", "Other"],
    "Gurgaon Paper Mills": ["Government", "Other"]
}

OUTPUT_UNIT_AGENCIES = {
    "Pratapgarh": ["Krishna Construction Company", "Other"],
    "Mujeri": ["Grow Max", "Other"]
}
DEFAULT_REPORTED_BY = ["Krishan JE", "Parveen JE", "Arun", "Rishi Sharma", "Other"]
