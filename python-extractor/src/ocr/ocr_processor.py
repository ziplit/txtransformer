"""
OCR processor using Tesseract with image preprocessing
"""

import logging
import asyncio
import time
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path
import tempfile
import os

import pytesseract
import cv2
import numpy as np
from PIL import Image

from ..config import settings
from .image_preprocessor import ImagePreprocessor
from .quality_assessor import ImageQualityAssessor


class OCRProcessor:
    """OCR processor with Tesseract and image preprocessing"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.preprocessor = ImagePreprocessor()
        self.quality_assessor = ImageQualityAssessor()
        
        # Configure Tesseract
        if settings.tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd
        
        self.logger.info("OCR Processor initialized", extra={
            "tesseract_version": self._get_tesseract_version(),
            "languages": settings.ocr_languages
        })
    
    def _get_tesseract_version(self) -> str:
        """Get Tesseract version"""
        try:
            return str(pytesseract.get_tesseract_version())
        except Exception:
            return "unknown"
    
    async def extract_text_from_image(
        self, 
        image_data: bytes, 
        language: Optional[str] = None,
        preprocessing: bool = True,
        quality_threshold: float = 0.3
    ) -> Dict[str, Any]:
        """
        Extract text from image using OCR with optional preprocessing
        
        Args:
            image_data: Raw image bytes
            language: OCR language (defaults to settings)
            preprocessing: Whether to apply image preprocessing
            quality_threshold: Minimum quality score to proceed with OCR
            
        Returns:
            Dictionary with extracted text, confidence, and metadata
        """
        start_time = time.time()
        
        try:
            # Load image
            image = await asyncio.get_event_loop().run_in_executor(
                None, self._load_image_from_bytes, image_data
            )
            
            if image is None:
                return self._create_error_result("Failed to load image")
            
            # Assess image quality
            quality_score = self.quality_assessor.assess_quality(image)
            
            self.logger.info("Image quality assessed", extra={
                "quality_score": quality_score,
                "threshold": quality_threshold
            })
            
            if quality_score < quality_threshold:
                self.logger.warning("Image quality below threshold", extra={
                    "quality_score": quality_score,
                    "threshold": quality_threshold
                })
            
            # Apply preprocessing if requested
            processed_image = image
            preprocessing_applied = []
            
            if preprocessing:
                processed_image, preprocessing_applied = await asyncio.get_event_loop().run_in_executor(
                    None, self._preprocess_image, image, quality_score
                )
            
            # Perform OCR
            ocr_result = await asyncio.get_event_loop().run_in_executor(
                None, self._perform_ocr, processed_image, language or settings.ocr_languages
            )
            
            processing_time = (time.time() - start_time) * 1000
            
            return {
                "success": True,
                "text": ocr_result["text"],
                "confidence": ocr_result["confidence"],
                "metadata": {
                    "processing_time_ms": processing_time,
                    "image_quality_score": quality_score,
                    "preprocessing_applied": preprocessing_applied,
                    "language": language or settings.ocr_languages,
                    "tesseract_version": self._get_tesseract_version(),
                    "image_size": {"width": image.shape[1], "height": image.shape[0]}
                },
                "word_details": ocr_result.get("word_details", [])
            }
            
        except Exception as e:
            error_msg = f"OCR processing failed: {str(e)}"
            self.logger.error(error_msg, extra={
                "error_type": type(e).__name__
            })
            return self._create_error_result(error_msg)
    
    async def extract_text_from_pdf_page(
        self, 
        pdf_path: Path, 
        page_number: int,
        fallback_ocr: bool = True
    ) -> Dict[str, Any]:
        """
        Extract text from a specific PDF page with OCR fallback
        
        Args:
            pdf_path: Path to PDF file
            page_number: Page number (0-indexed)
            fallback_ocr: Whether to use OCR if text extraction fails
            
        Returns:
            Dictionary with extracted text and metadata
        """
        try:
            # First try regular text extraction
            text_result = await self._extract_pdf_text(pdf_path, page_number)
            
            # If text extraction is poor or fails, use OCR
            if fallback_ocr and (not text_result["text"].strip() or len(text_result["text"]) < 50):
                self.logger.info("Falling back to OCR for PDF page", extra={
                    "page_number": page_number,
                    "text_length": len(text_result["text"])
                })
                
                # Convert PDF page to image and OCR
                image_data = await self._pdf_page_to_image(pdf_path, page_number)
                ocr_result = await self.extract_text_from_image(image_data)
                
                if ocr_result["success"]:
                    return {
                        "success": True,
                        "text": ocr_result["text"],
                        "method": "ocr",
                        "metadata": {
                            **ocr_result["metadata"],
                            "fallback_used": True,
                            "original_text_length": len(text_result["text"])
                        }
                    }
            
            return {
                "success": True,
                "text": text_result["text"],
                "method": "text_extraction",
                "metadata": {"fallback_used": False}
            }
            
        except Exception as e:
            error_msg = f"PDF OCR processing failed: {str(e)}"
            self.logger.error(error_msg)
            return self._create_error_result(error_msg)
    
    def _load_image_from_bytes(self, image_data: bytes) -> Optional[np.ndarray]:
        """Load image from bytes using OpenCV"""
        try:
            # Convert bytes to numpy array
            nparr = np.frombuffer(image_data, np.uint8)
            # Decode image
            image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            return image
        except Exception as e:
            self.logger.error(f"Failed to load image: {e}")
            return None
    
    def _preprocess_image(self, image: np.ndarray, quality_score: float) -> Tuple[np.ndarray, List[str]]:
        """Apply preprocessing based on image quality"""
        preprocessing_steps = []
        processed_image = image.copy()
        
        # Apply different preprocessing based on quality
        if quality_score < 0.5:
            # Low quality image - aggressive preprocessing
            processed_image = self.preprocessor.enhance_low_quality_image(processed_image)
            preprocessing_steps.extend([
                "noise_reduction", "contrast_enhancement", 
                "sharpening", "binarization"
            ])
        elif quality_score < 0.7:
            # Medium quality - moderate preprocessing
            processed_image = self.preprocessor.enhance_medium_quality_image(processed_image)
            preprocessing_steps.extend(["contrast_enhancement", "binarization"])
        else:
            # High quality - minimal preprocessing
            processed_image = self.preprocessor.enhance_high_quality_image(processed_image)
            preprocessing_steps.append("binarization")
        
        return processed_image, preprocessing_steps
    
    def _perform_ocr(self, image: np.ndarray, language: str) -> Dict[str, Any]:
        """Perform OCR on preprocessed image"""
        try:
            # Configure OCR parameters
            config = f'--oem 3 --psm 6 -l {language}'
            
            # Extract text with confidence
            text = pytesseract.image_to_string(image, config=config)
            
            # Get detailed word information
            word_data = pytesseract.image_to_data(image, config=config, output_type=pytesseract.Output.DICT)
            
            # Calculate average confidence
            confidences = [int(conf) for conf in word_data['conf'] if int(conf) > 0]
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0
            
            # Extract word details
            word_details = []
            for i in range(len(word_data['text'])):
                if int(word_data['conf'][i]) > 0:
                    word_details.append({
                        "text": word_data['text'][i],
                        "confidence": int(word_data['conf'][i]),
                        "bbox": {
                            "x": int(word_data['left'][i]),
                            "y": int(word_data['top'][i]),
                            "width": int(word_data['width'][i]),
                            "height": int(word_data['height'][i])
                        }
                    })
            
            return {
                "text": text.strip(),
                "confidence": avg_confidence,
                "word_details": word_details
            }
            
        except Exception as e:
            self.logger.error(f"OCR processing failed: {e}")
            raise
    
    async def _extract_pdf_text(self, pdf_path: Path, page_number: int) -> Dict[str, Any]:
        """Extract text from PDF page using standard method"""
        # This would use a PDF library like PyPDF2 or pdfplumber
        # For now, return empty to force OCR fallback
        return {"text": "", "method": "text_extraction"}
    
    async def _pdf_page_to_image(self, pdf_path: Path, page_number: int) -> bytes:
        """Convert PDF page to image bytes for OCR"""
        try:
            # Use pdf2image to convert PDF page to image
            from pdf2image import convert_from_path
            
            pages = convert_from_path(str(pdf_path), first_page=page_number+1, last_page=page_number+1)
            if not pages:
                raise ValueError(f"Could not convert PDF page {page_number}")
            
            # Convert PIL image to bytes
            import io
            img_bytes = io.BytesIO()
            pages[0].save(img_bytes, format='PNG')
            return img_bytes.getvalue()
            
        except ImportError:
            raise ImportError("pdf2image is required for PDF to image conversion")
        except Exception as e:
            self.logger.error(f"PDF to image conversion failed: {e}")
            raise
    
    def _create_error_result(self, error_msg: str) -> Dict[str, Any]:
        """Create error result dictionary"""
        return {
            "success": False,
            "text": "",
            "confidence": 0,
            "error": error_msg,
            "metadata": {},
            "word_details": []
        }
    
    def get_supported_languages(self) -> List[str]:
        """Get list of supported OCR languages"""
        try:
            return pytesseract.get_languages()
        except Exception:
            return [settings.ocr_languages]