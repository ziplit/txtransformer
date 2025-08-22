"""
Health checking system for the Email Extractor service
"""

import asyncio
import logging
import time
from typing import Dict, Any, List, Optional
import os
import sys

from .config import settings


class HealthChecker:
    """Comprehensive health checking for the service"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.startup_time = time.time()
        
    async def check_health(self) -> Dict[str, Any]:
        """
        Basic health check - service is alive
        Returns quickly with minimal resource usage
        """
        health_status = {
            "healthy": True,
            "timestamp": time.time(),
            "uptime_seconds": time.time() - self.startup_time,
            "service": "email-extractor",
            "version": "0.1.0"
        }
        
        try:
            # Basic system checks
            basic_checks = await self._run_basic_checks()
            health_status.update(basic_checks)
            
            # If any critical check fails, mark as unhealthy
            if any(not check.get("passed", True) for check in basic_checks.get("checks", {}).values()):
                health_status["healthy"] = False
                
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            health_status["healthy"] = False
            health_status["error"] = str(e)
            
        return health_status
    
    async def check_readiness(self) -> Dict[str, Any]:
        """
        Readiness check - service is ready to handle requests
        More comprehensive than health check
        """
        readiness_status = {
            "ready": True,
            "timestamp": time.time(),
            "uptime_seconds": time.time() - self.startup_time,
            "service": "email-extractor",
            "version": "0.1.0"
        }
        
        try:
            # Run all readiness checks with timeout
            checks_task = asyncio.create_task(self._run_readiness_checks())
            checks = await asyncio.wait_for(
                checks_task, 
                timeout=settings.readiness_check_timeout
            )
            
            readiness_status.update(checks)
            
            # If any critical dependency fails, mark as not ready
            failed_checks = [
                name for name, check in checks.get("dependencies", {}).items()
                if not check.get("available", True)
            ]
            
            if failed_checks:
                readiness_status["ready"] = False
                readiness_status["failed_dependencies"] = failed_checks
                
        except asyncio.TimeoutError:
            self.logger.warning(f"Readiness check timed out after {settings.readiness_check_timeout}s")
            readiness_status["ready"] = False
            readiness_status["error"] = "Readiness check timeout"
            
        except Exception as e:
            self.logger.error(f"Readiness check failed: {e}")
            readiness_status["ready"] = False
            readiness_status["error"] = str(e)
            
        return readiness_status
    
    async def _run_basic_checks(self) -> Dict[str, Any]:
        """Run basic health checks"""
        checks = {}
        
        # Memory check
        try:
            import psutil
            memory = psutil.virtual_memory()
            checks["memory"] = {
                "passed": memory.percent < 95,
                "usage_percent": memory.percent,
                "available_mb": memory.available // (1024 * 1024)
            }
        except ImportError:
            checks["memory"] = {"passed": True, "note": "psutil not available"}
        except Exception as e:
            checks["memory"] = {"passed": False, "error": str(e)}
        
        # Disk space check (temp directory)
        try:
            temp_dir = settings.temp_dir
            os.makedirs(temp_dir, exist_ok=True)
            
            if hasattr(os, 'statvfs'):
                statvfs = os.statvfs(temp_dir)
                free_space = statvfs.f_frsize * statvfs.f_bavail
                total_space = statvfs.f_frsize * statvfs.f_blocks
                usage_percent = ((total_space - free_space) / total_space) * 100
                
                checks["disk"] = {
                    "passed": usage_percent < 95,
                    "usage_percent": usage_percent,
                    "free_mb": free_space // (1024 * 1024),
                    "temp_dir": temp_dir
                }
            else:
                checks["disk"] = {"passed": True, "note": "Disk check not available on this platform"}
                
        except Exception as e:
            checks["disk"] = {"passed": False, "error": str(e)}
        
        return {"checks": checks}
    
    async def _run_readiness_checks(self) -> Dict[str, Any]:
        """Run comprehensive readiness checks"""
        dependencies = {}
        
        # Check Python dependencies
        dependencies["python"] = await self._check_python_env()
        
        # Check OCR capabilities
        if settings.ocr_enabled:
            dependencies["tesseract"] = await self._check_tesseract()
            dependencies["opencv"] = await self._check_opencv()
            dependencies["pdf2image"] = await self._check_pdf2image()
        
        # Check spaCy model
        dependencies["spacy"] = await self._check_spacy_model()
        
        # Check temp directory writability
        dependencies["temp_storage"] = await self._check_temp_storage()
        
        # Check table extraction dependencies
        dependencies["camelot"] = await self._check_camelot()
        dependencies["pdfplumber"] = await self._check_pdfplumber()
        
        # Check deterministic extraction dependencies
        dependencies["postal"] = await self._check_postal()
        dependencies["dateparser"] = await self._check_dateparser()
        dependencies["price_parser"] = await self._check_price_parser()
        
        return {"dependencies": dependencies}
    
    async def _check_python_env(self) -> Dict[str, Any]:
        """Check Python environment and critical imports"""
        try:
            python_version = sys.version_info
            
            # Try importing critical dependencies
            critical_imports = []
            try:
                import fastapi
                critical_imports.append(f"fastapi=={fastapi.__version__}")
            except ImportError as e:
                return {"available": False, "error": f"Missing fastapi: {e}"}
            
            try:
                import pydantic
                critical_imports.append(f"pydantic=={pydantic.__version__}")
            except ImportError as e:
                return {"available": False, "error": f"Missing pydantic: {e}"}
            
            return {
                "available": True,
                "python_version": f"{python_version.major}.{python_version.minor}.{python_version.micro}",
                "imports": critical_imports
            }
            
        except Exception as e:
            return {"available": False, "error": str(e)}
    
    async def _check_tesseract(self) -> Dict[str, Any]:
        """Check Tesseract OCR availability"""
        try:
            import pytesseract
            
            # Try to get tesseract version
            version = pytesseract.get_tesseract_version()
            
            return {
                "available": True,
                "version": str(version),
                "languages": settings.ocr_languages
            }
            
        except ImportError:
            return {"available": False, "error": "pytesseract not installed"}
        except Exception as e:
            return {"available": False, "error": str(e)}
    
    async def _check_spacy_model(self) -> Dict[str, Any]:
        """Check spaCy model availability"""
        try:
            import spacy
            
            # Try to load the configured model
            nlp = spacy.load(settings.spacy_model)
            
            return {
                "available": True,
                "model": settings.spacy_model,
                "version": spacy.__version__
            }
            
        except ImportError:
            return {"available": False, "error": "spacy not installed"}
        except OSError as e:
            if "model" in str(e).lower():
                return {
                    "available": False,
                    "error": f"spaCy model '{settings.spacy_model}' not found. Run: python -m spacy download {settings.spacy_model}"
                }
            return {"available": False, "error": str(e)}
        except Exception as e:
            return {"available": False, "error": str(e)}
    
    async def _check_opencv(self) -> Dict[str, Any]:
        """Check OpenCV availability for image processing"""
        try:
            import cv2
            
            return {
                "available": True,
                "version": cv2.__version__,
                "build_info": "OpenCV available for image preprocessing"
            }
            
        except ImportError:
            return {"available": False, "error": "opencv-python not installed"}
        except Exception as e:
            return {"available": False, "error": str(e)}
    
    async def _check_pdf2image(self) -> Dict[str, Any]:
        """Check pdf2image availability for PDF to image conversion"""
        try:
            import pdf2image
            
            # Try to check if poppler is available (required by pdf2image)
            try:
                from pdf2image.exceptions import PDFInfoNotInstalledError
                # This will raise an exception if poppler is not installed
                pdf2image.pdfinfo_from_path("nonexistent.pdf")
            except PDFInfoNotInstalledError:
                return {
                    "available": False,
                    "error": "poppler-utils not installed. Install with: brew install poppler (macOS) or apt-get install poppler-utils (Ubuntu)"
                }
            except:
                # Other errors are expected for non-existent file
                pass
            
            return {
                "available": True,
                "module": "pdf2image",
                "note": "PDF to image conversion available"
            }
            
        except ImportError:
            return {"available": False, "error": "pdf2image not installed"}
        except Exception as e:
            return {"available": False, "error": str(e)}
    
    async def _check_temp_storage(self) -> Dict[str, Any]:
        """Check temporary storage availability"""
        try:
            temp_dir = settings.temp_dir
            os.makedirs(temp_dir, exist_ok=True)
            
            # Try writing a test file
            test_file = os.path.join(temp_dir, "health_check.tmp")
            with open(test_file, 'w') as f:
                f.write("test")
            
            # Clean up test file
            os.remove(test_file)
            
            return {
                "available": True,
                "temp_dir": temp_dir,
                "writable": True
            }
            
        except Exception as e:
            return {"available": False, "error": str(e)}
    
    async def _check_camelot(self) -> Dict[str, Any]:
        """Check Camelot table extraction availability"""
        try:
            import camelot
            
            return {
                "available": True,
                "version": getattr(camelot, '__version__', 'unknown'),
                "note": "Camelot table extraction available"
            }
            
        except ImportError:
            return {"available": False, "error": "camelot-py not installed"}
        except Exception as e:
            return {"available": False, "error": str(e)}
    
    async def _check_pdfplumber(self) -> Dict[str, Any]:
        """Check pdfplumber availability for fallback table extraction"""
        try:
            import pdfplumber
            
            return {
                "available": True,
                "version": getattr(pdfplumber, '__version__', 'unknown'),
                "note": "pdfplumber fallback extraction available"
            }
            
        except ImportError:
            return {"available": False, "error": "pdfplumber not installed"}
        except Exception as e:
            return {"available": False, "error": str(e)}
    
    async def _check_postal(self) -> Dict[str, Any]:
        """Check postal (libpostal) availability for address parsing"""
        try:
            import postal.parser
            import postal.expand
            
            return {
                "available": True,
                "modules": ["postal.parser", "postal.expand"],
                "note": "libpostal available for address parsing"
            }
            
        except ImportError:
            return {
                "available": False, 
                "error": "postal not installed. Install with: pip install postal",
                "note": "Address extraction will use regex fallback"
            }
        except Exception as e:
            return {"available": False, "error": str(e)}
    
    async def _check_dateparser(self) -> Dict[str, Any]:
        """Check dateparser availability for flexible date parsing"""
        try:
            import dateparser
            
            # Test basic parsing
            test_date = dateparser.parse("January 1, 2024")
            
            return {
                "available": True,
                "version": getattr(dateparser, '__version__', 'unknown'),
                "test_successful": test_date is not None
            }
            
        except ImportError:
            return {
                "available": False,
                "error": "dateparser not installed", 
                "note": "Date extraction will use regex fallback"
            }
        except Exception as e:
            return {"available": False, "error": str(e)}
    
    async def _check_price_parser(self) -> Dict[str, Any]:
        """Check price-parser availability for monetary value parsing"""
        try:
            from price_parser import Price
            
            # Test basic parsing
            test_price = Price.fromstring("$19.99")
            
            return {
                "available": True,
                "test_successful": test_price.amount is not None,
                "test_amount": str(test_price.amount) if test_price.amount else None
            }
            
        except ImportError:
            return {
                "available": False,
                "error": "price-parser not installed",
                "note": "Price extraction will use regex fallback"
            }
        except Exception as e:
            return {"available": False, "error": str(e)}