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
    Processes a weighment slip image. Tries 4 rotations (0, 90, 180, 270)
    to find the one that yields the most OCR fields. If the best rotation
    is not 0, it permanently rotates the image so it is displayed horizontally.
    """
    if ocr_engine is None:
        return {"error": "OCR engine not initialized."}
        
    try:
        best_overall_results = {
            "rst_no": None,
            "vehicle_no": None,
            "net_weight": None,
            "score": -1
        }
        best_angle = 0
        
        # Test 4 standard rotations
        for angle in [0, 90, 180, 270]:
            img = cv2.imread(image_path)
            if img is None:
                continue
                
            if angle == 90:
                img = cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
            elif angle == 180:
                img = cv2.rotate(img, cv2.ROTATE_180)
            elif angle == 270:
                img = cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
                
            temp_path = os.path.join(tempfile.gettempdir(), f"temp_rot_{angle}.jpg")
            cv2.imwrite(temp_path, img)
            
            image_versions = preprocess_image(temp_path)
            current_results = {"rst_no": None, "vehicle_no": None, "net_weight": None, "agency_name": None}
            
            for img_version in image_versions:
                result = ocr_engine.ocr(img_version, cls=True)
                if not result or not result[0]:
                    continue
                    
                text_blocks = [line[1][0] for line in result[0]]
                extracted = extract_fields(text_blocks)
                
                if not current_results["rst_no"]: current_results["rst_no"] = extracted["rst_no"]
                if not current_results["vehicle_no"]: current_results["vehicle_no"] = extracted["vehicle_no"]
                if not current_results["net_weight"]: current_results["net_weight"] = extracted["net_weight"]
                if not current_results.get("agency_name"): current_results["agency_name"] = extracted.get("agency_name")
                
                if current_results["rst_no"] and current_results["vehicle_no"] and current_results["net_weight"]:
                    break
            
            # Delete temporary file
            try:
                os.remove(temp_path)
            except:
                pass
                
            # Score this rotation
            score = sum(1 for v in current_results.values() if v)
            if score > best_overall_results["score"]:
                best_overall_results = current_results
                best_overall_results["score"] = score
                best_angle = angle
                
            if score == 3:
                break # Found everything, no need to test other rotations
                
        # If the best angle was not 0, permanently rotate the original image
        if best_angle != 0:
            rotate_image_file(image_path, best_angle)
            
        return {
            "rst_no": best_overall_results["rst_no"],
            "vehicle_no": best_overall_results["vehicle_no"],
            "net_weight": best_overall_results["net_weight"],
            "agency_name": best_overall_results.get("agency_name")
        }
        
    except Exception as e:
        print(f"Error during OCR processing: {e}")
        return {"error": str(e)}
