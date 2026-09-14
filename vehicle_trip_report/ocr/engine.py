from ocr.preprocessing import preprocess_image
from ocr.extractor import extract_fields
import cv2
import tempfile
import os
import logging

# Suppress PaddleOCR warnings about the disabled angle classifier
logging.getLogger('ppocr').setLevel(logging.ERROR)

def rotate_image_file(image_path, angle):
    """Rotates the image and overwrites the file."""
    img = cv2.imread(image_path)
    if img is None:
        return
    if angle == 90:
        img = cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
    elif angle == 180:
        img = cv2.rotate(img, cv2.ROTATE_180)
    elif angle == 270:
        img = cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
    cv2.imwrite(image_path, img)

def process_slip(image_path, ocr_engine):
    """
    Processes a weighment slip image using PaddleOCR's built-in angle classifier.
    Tests up to 3 preprocessing variations and stops early if all fields are found.
    """
    if ocr_engine is None:
        return {"error": "OCR engine not initialized."}
        
    try:
        best_overall_results = {
            "rst_no": None,
            "vehicle_no": None,
            "net_weight": None,
            "agency_name": None
        }
        
        image_versions = preprocess_image(image_path)
        
        for img_version in image_versions:
            # cls=True uses PaddleOCR's angle classifier
            result = ocr_engine.ocr(img_version, cls=True)
            if not result or not result[0]:
                continue
                
            text_blocks = [line[1][0] for line in result[0]]
            extracted = extract_fields(text_blocks)
            
            if not best_overall_results["rst_no"]: best_overall_results["rst_no"] = extracted.get("rst_no")
            if not best_overall_results["vehicle_no"]: best_overall_results["vehicle_no"] = extracted.get("vehicle_no")
            if not best_overall_results["net_weight"]: best_overall_results["net_weight"] = extracted.get("net_weight")
            if not best_overall_results.get("agency_name"): best_overall_results["agency_name"] = extracted.get("agency_name")
            
            # If we found all 3 required fields, we can stop immediately
            if best_overall_results["rst_no"] and best_overall_results["vehicle_no"] and best_overall_results["net_weight"]:
                break
                
        return best_overall_results
        
    except Exception as e:
        print(f"Error during OCR processing: {e}")
        return {"error": str(e)}
