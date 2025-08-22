"""
Image quality assessment for OCR preprocessing decisions
"""

import logging
import cv2
import numpy as np
from typing import Dict, Any


class ImageQualityAssessor:
    """Assess image quality to determine optimal OCR preprocessing"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def assess_quality(self, image: np.ndarray) -> float:
        """
        Assess overall image quality for OCR
        
        Returns:
            Quality score between 0.0 (poor) and 1.0 (excellent)
        """
        metrics = self.get_quality_metrics(image)
        
        # Weighted combination of quality metrics
        weights = {
            "sharpness": 0.3,
            "contrast": 0.25,
            "brightness": 0.2,
            "noise_level": 0.15,
            "resolution": 0.1
        }
        
        quality_score = (
            weights["sharpness"] * metrics["sharpness_score"] +
            weights["contrast"] * metrics["contrast_score"] +
            weights["brightness"] * metrics["brightness_score"] +
            weights["noise_level"] * (1.0 - metrics["noise_level"]) +  # Invert noise (less noise = better)
            weights["resolution"] * metrics["resolution_score"]
        )
        
        # Clamp to [0, 1] range
        quality_score = max(0.0, min(1.0, quality_score))
        
        self.logger.debug("Image quality assessment", extra={
            "overall_score": quality_score,
            "metrics": metrics
        })
        
        return quality_score
    
    def get_quality_metrics(self, image: np.ndarray) -> Dict[str, Any]:
        """Get detailed quality metrics for an image"""
        # Convert to grayscale if needed
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image
        
        metrics = {}
        
        # Sharpness (using Laplacian variance)
        metrics["sharpness"] = self._calculate_sharpness(gray)
        metrics["sharpness_score"] = self._normalize_sharpness(metrics["sharpness"])
        
        # Contrast (using standard deviation)
        metrics["contrast"] = self._calculate_contrast(gray)
        metrics["contrast_score"] = self._normalize_contrast(metrics["contrast"])
        
        # Brightness (using mean pixel value)
        metrics["brightness"] = self._calculate_brightness(gray)
        metrics["brightness_score"] = self._normalize_brightness(metrics["brightness"])
        
        # Noise level estimation
        metrics["noise_level"] = self._estimate_noise_level(gray)
        
        # Resolution assessment
        metrics["resolution"] = {"width": gray.shape[1], "height": gray.shape[0]}
        metrics["resolution_score"] = self._assess_resolution(gray.shape)
        
        # Additional metrics
        metrics["blur_detection"] = self._detect_blur(gray)
        metrics["text_density"] = self._estimate_text_density(gray)
        
        return metrics
    
    def _calculate_sharpness(self, image: np.ndarray) -> float:
        """Calculate image sharpness using Laplacian variance"""
        laplacian = cv2.Laplacian(image, cv2.CV_64F)
        return laplacian.var()
    
    def _normalize_sharpness(self, sharpness: float) -> float:
        """Normalize sharpness score to [0, 1]"""
        # Based on empirical observation, good sharpness is > 500, excellent > 1000
        if sharpness > 1000:
            return 1.0
        elif sharpness > 500:
            return 0.7 + 0.3 * (sharpness - 500) / 500
        elif sharpness > 100:
            return 0.3 + 0.4 * (sharpness - 100) / 400
        else:
            return sharpness / 100 * 0.3
    
    def _calculate_contrast(self, image: np.ndarray) -> float:
        """Calculate image contrast using standard deviation"""
        return np.std(image)
    
    def _normalize_contrast(self, contrast: float) -> float:
        """Normalize contrast score to [0, 1]"""
        # Good contrast is typically > 50, excellent > 80
        if contrast > 80:
            return 1.0
        elif contrast > 50:
            return 0.7 + 0.3 * (contrast - 50) / 30
        elif contrast > 20:
            return 0.3 + 0.4 * (contrast - 20) / 30
        else:
            return contrast / 20 * 0.3
    
    def _calculate_brightness(self, image: np.ndarray) -> float:
        """Calculate average brightness"""
        return np.mean(image)
    
    def _normalize_brightness(self, brightness: float) -> float:
        """Normalize brightness score to [0, 1]"""
        # Optimal brightness is around 120-140 for OCR
        optimal_range = (120, 140)
        
        if optimal_range[0] <= brightness <= optimal_range[1]:
            return 1.0
        elif 100 <= brightness < optimal_range[0]:
            return 0.7 + 0.3 * (brightness - 100) / (optimal_range[0] - 100)
        elif optimal_range[1] < brightness <= 160:
            return 1.0 - 0.3 * (brightness - optimal_range[1]) / (160 - optimal_range[1])
        elif 80 <= brightness < 100:
            return 0.3 + 0.4 * (brightness - 80) / 20
        elif 160 < brightness <= 180:
            return 0.4 + 0.3 * (180 - brightness) / 20
        else:
            return max(0.0, 0.3 - abs(brightness - 130) / 130 * 0.3)
    
    def _estimate_noise_level(self, image: np.ndarray) -> float:
        """Estimate noise level in image"""
        # Use median filter to estimate noise
        median_filtered = cv2.medianBlur(image, 5)
        noise = cv2.absdiff(image, median_filtered)
        return np.mean(noise) / 255.0  # Normalize to [0, 1]
    
    def _assess_resolution(self, shape: tuple) -> float:
        """Assess if resolution is adequate for OCR"""
        height, width = shape
        total_pixels = height * width
        
        # Good resolution for OCR is typically > 300 DPI equivalent
        # For text, minimum recommended is around 150-200 DPI
        if total_pixels > 2000000:  # Very high resolution
            return 1.0
        elif total_pixels > 1000000:  # High resolution
            return 0.9
        elif total_pixels > 500000:  # Medium resolution
            return 0.7
        elif total_pixels > 200000:  # Low but acceptable
            return 0.5
        else:  # Too low for good OCR
            return 0.2
    
    def _detect_blur(self, image: np.ndarray) -> Dict[str, Any]:
        """Detect different types of blur"""
        # Motion blur detection using directional gradients
        grad_x = cv2.Sobel(image, cv2.CV_64F, 1, 0, ksize=3)
        grad_y = cv2.Sobel(image, cv2.CV_64F, 0, 1, ksize=3)
        
        motion_blur_x = np.var(grad_x)
        motion_blur_y = np.var(grad_y)
        
        # General blur using Laplacian
        laplacian_var = cv2.Laplacian(image, cv2.CV_64F).var()
        
        return {
            "motion_blur_horizontal": motion_blur_x,
            "motion_blur_vertical": motion_blur_y,
            "general_blur": laplacian_var,
            "is_blurry": laplacian_var < 100  # Threshold for blur detection
        }
    
    def _estimate_text_density(self, image: np.ndarray) -> float:
        """Estimate density of text in the image"""
        # Apply threshold to create binary image
        _, binary = cv2.threshold(image, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # Count text pixels (assuming text is black on white background)
        text_pixels = np.sum(binary == 0)  # Black pixels
        total_pixels = binary.size
        
        text_density = text_pixels / total_pixels
        return text_density
    
    def recommend_preprocessing(self, image: np.ndarray) -> Dict[str, Any]:
        """
        Recommend preprocessing steps based on image quality assessment
        
        Returns:
            Dictionary with recommended preprocessing steps and parameters
        """
        metrics = self.get_quality_metrics(image)
        recommendations = {
            "steps": [],
            "priority": "medium",
            "confidence": 0.7
        }
        
        # Determine recommendations based on metrics
        if metrics["sharpness_score"] < 0.5:
            recommendations["steps"].append("sharpening")
            recommendations["priority"] = "high"
        
        if metrics["contrast_score"] < 0.6:
            recommendations["steps"].append("contrast_enhancement")
        
        if metrics["noise_level"] > 0.3:
            recommendations["steps"].append("noise_reduction")
        
        if metrics["brightness_score"] < 0.6:
            recommendations["steps"].append("brightness_correction")
        
        if metrics["blur_detection"]["is_blurry"]:
            recommendations["steps"].append("deblur")
            recommendations["priority"] = "high"
        
        # Always recommend binarization for OCR
        recommendations["steps"].append("binarization")
        
        # Set priority based on overall quality
        overall_quality = self.assess_quality(image)
        if overall_quality < 0.3:
            recommendations["priority"] = "critical"
            recommendations["confidence"] = 0.9
        elif overall_quality < 0.6:
            recommendations["priority"] = "high" 
            recommendations["confidence"] = 0.8
        
        return recommendations