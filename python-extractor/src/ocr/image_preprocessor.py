"""
Image preprocessing for improved OCR accuracy
"""

import logging
import cv2
import numpy as np
from typing import Tuple


class ImagePreprocessor:
    """Image preprocessing utilities for OCR enhancement"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def enhance_low_quality_image(self, image: np.ndarray) -> np.ndarray:
        """Apply aggressive preprocessing for low quality images"""
        # Convert to grayscale
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image
        
        # Noise reduction
        denoised = cv2.fastNlMeansDenoising(gray)
        
        # Contrast enhancement using CLAHE
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
        enhanced = clahe.apply(denoised)
        
        # Sharpening
        sharpened = self._apply_sharpening(enhanced)
        
        # Adaptive binarization
        binary = cv2.adaptiveThreshold(
            sharpened, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
        )
        
        # Morphological operations to clean up
        kernel = np.ones((2,2), np.uint8)
        cleaned = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
        
        return cleaned
    
    def enhance_medium_quality_image(self, image: np.ndarray) -> np.ndarray:
        """Apply moderate preprocessing for medium quality images"""
        # Convert to grayscale
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image
        
        # Contrast enhancement
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        enhanced = clahe.apply(gray)
        
        # Adaptive binarization
        binary = cv2.adaptiveThreshold(
            enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
        )
        
        return binary
    
    def enhance_high_quality_image(self, image: np.ndarray) -> np.ndarray:
        """Apply minimal preprocessing for high quality images"""
        # Convert to grayscale
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image
        
        # Simple binarization
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        return binary
    
    def _apply_sharpening(self, image: np.ndarray) -> np.ndarray:
        """Apply sharpening filter"""
        kernel = np.array([[-1,-1,-1],
                          [-1, 9,-1],
                          [-1,-1,-1]])
        sharpened = cv2.filter2D(image, -1, kernel)
        return sharpened
    
    def deskew_image(self, image: np.ndarray) -> Tuple[np.ndarray, float]:
        """
        Detect and correct skew in image
        
        Returns:
            Tuple of (deskewed_image, skew_angle)
        """
        try:
            # Convert to grayscale if needed
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image
            
            # Apply threshold to get binary image
            _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            # Invert if necessary (text should be black on white background)
            if np.mean(binary) > 127:
                binary = cv2.bitwise_not(binary)
            
            # Find contours and get the largest one
            contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            if not contours:
                return image, 0.0
            
            # Get the largest contour (assumed to be the main text area)
            largest_contour = max(contours, key=cv2.contourArea)
            
            # Get the minimum area rectangle
            rect = cv2.minAreaRect(largest_contour)
            angle = rect[2]
            
            # Correct angle (OpenCV returns angle between -90 and 0)
            if angle < -45:
                angle = 90 + angle
            
            # Only correct if angle is significant
            if abs(angle) > 0.5:  # Only deskew if more than 0.5 degrees
                # Get rotation matrix
                h, w = image.shape[:2]
                center = (w // 2, h // 2)
                rotation_matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
                
                # Apply rotation
                deskewed = cv2.warpAffine(image, rotation_matrix, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
                
                self.logger.info(f"Applied deskewing correction", extra={"angle": angle})
                return deskewed, angle
            else:
                return image, angle
                
        except Exception as e:
            self.logger.warning(f"Deskewing failed: {e}")
            return image, 0.0
    
    def remove_noise(self, image: np.ndarray, method: str = "gaussian") -> np.ndarray:
        """
        Remove noise from image using various methods
        
        Args:
            image: Input image
            method: Noise removal method ("gaussian", "median", "bilateral")
        """
        if method == "gaussian":
            return cv2.GaussianBlur(image, (5, 5), 0)
        elif method == "median":
            return cv2.medianBlur(image, 5)
        elif method == "bilateral":
            return cv2.bilateralFilter(image, 9, 75, 75)
        else:
            return image
    
    def resize_for_ocr(self, image: np.ndarray, target_dpi: int = 300) -> np.ndarray:
        """
        Resize image to optimal DPI for OCR
        
        Args:
            image: Input image
            target_dpi: Target DPI (300 is generally optimal for OCR)
        """
        h, w = image.shape[:2]
        
        # Estimate current DPI (assuming typical screen DPI of 72-96)
        current_dpi = 96  # Default assumption
        
        # Calculate scale factor
        scale_factor = target_dpi / current_dpi
        
        # Only resize if the change is significant
        if abs(scale_factor - 1.0) > 0.1:
            new_w = int(w * scale_factor)
            new_h = int(h * scale_factor)
            
            resized = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
            
            self.logger.info(f"Resized image for OCR", extra={
                "original_size": (w, h),
                "new_size": (new_w, new_h),
                "scale_factor": scale_factor
            })
            
            return resized
        
        return image
    
    def enhance_contrast(self, image: np.ndarray, method: str = "clahe") -> np.ndarray:
        """
        Enhance image contrast using various methods
        
        Args:
            image: Input image (grayscale)
            method: Enhancement method ("clahe", "histogram_eq", "gamma")
        """
        if method == "clahe":
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
            return clahe.apply(image)
        elif method == "histogram_eq":
            return cv2.equalizeHist(image)
        elif method == "gamma":
            # Gamma correction (gamma = 1.2 for slight brightening)
            gamma = 1.2
            lookup_table = np.array([((i / 255.0) ** (1.0 / gamma)) * 255 for i in np.arange(0, 256)]).astype("uint8")
            return cv2.LUT(image, lookup_table)
        else:
            return image