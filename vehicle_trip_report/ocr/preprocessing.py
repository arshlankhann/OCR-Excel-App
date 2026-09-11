import cv2
import numpy as np

def preprocess_image(image_path):
    """
    Applies multiple preprocessing techniques to improve OCR accuracy.
    Returns a list of processed image paths (or numpy arrays) to try OCR on.
    We return multiple versions because OCR might fail on one but succeed on another.
    """
    img = cv2.imread(image_path)
    if img is None:
        return []

    processed_images = []
    
    # Version 1: Original image
    processed_images.append(img)
    
    # Version 2: Grayscale + Increased Contrast
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    alpha = 1.5 # Contrast control (1.0-3.0)
    beta = 0    # Brightness control (0-100)
    contrast = cv2.convertScaleAbs(gray, alpha=alpha, beta=beta)
    processed_images.append(contrast)
    
    # Version 3: Grayscale + Otsu Thresholding (Binarization)
    # Applying Gaussian blur before thresholding helps remove noise
    blur = cv2.GaussianBlur(gray, (5,5), 0)
    _, thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    processed_images.append(thresh)
    
    # Could add rotation/deskewing here if required, but PaddleOCR handles mild skew well.
    
    return processed_images
