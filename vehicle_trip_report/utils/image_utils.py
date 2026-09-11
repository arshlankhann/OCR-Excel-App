import os
from PIL import Image
import uuid
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import IMAGES_DIR, EXCEL_IMAGE_WIDTH, EXCEL_IMAGE_HEIGHT

def save_uploaded_image(uploaded_file):
    if uploaded_file is None:
        return None

    ext = os.path.splitext(uploaded_file.name)[1]
    if not ext:
        ext = ".jpg"
    unique_filename = f"{uuid.uuid4().hex}{ext}"
    
    file_path = IMAGES_DIR / unique_filename
    
    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
        
    return str(file_path)

def process_image_for_excel(image_path):
    if not os.path.exists(image_path):
        return None
        
    try:
        img = Image.open(image_path)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
            
        # Rotate if the image is vertical (portrait)
        if img.height > img.width:
            img = img.rotate(90, expand=True)
            
        img.thumbnail((EXCEL_IMAGE_WIDTH, EXCEL_IMAGE_HEIGHT), Image.Resampling.LANCZOS)
        
        temp_filename = f"temp_excel_{uuid.uuid4().hex}.jpg"
        temp_path = IMAGES_DIR / temp_filename
        
        img.save(temp_path, format="JPEG", quality=85)
        return str(temp_path)
    except Exception as e:
        print(f"Error processing image for excel: {e}")
        return None
