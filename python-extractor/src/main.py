"""
Email Extractor - Python sidecar for processing emails and attachments
"""

import logging
import sys
from contextlib import asynccontextmanager
from typing import Dict, Any

from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import JSONResponse
import uvicorn

from .config import settings
from .dependencies import get_health_checker, get_logger, get_processor_registry
from .health import HealthChecker
from .logger import setup_logging
from .processor_registry import ProcessorRegistry
from .processors.base_processor import ProcessingContext


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager"""
    # Startup
    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("Starting Email Extractor service", extra={
        "version": "0.1.0",
        "host": settings.host,
        "port": settings.port
    })
    
    yield
    
    # Shutdown
    logger.info("Shutting down Email Extractor service")


app = FastAPI(
    title="Email Extractor",
    version="0.1.0",
    description="Python sidecar for extracting structured data from emails and attachments",
    lifespan=lifespan
)


@app.get("/healthz")
async def health_check(health_checker: HealthChecker = Depends(get_health_checker)):
    """Health check endpoint - returns 200 if service is alive"""
    try:
        health_status = await health_checker.check_health()
        return JSONResponse(
            status_code=200 if health_status["healthy"] else 503,
            content=health_status
        )
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={"healthy": False, "error": str(e)}
        )


@app.get("/readyz")
async def readiness_check(health_checker: HealthChecker = Depends(get_health_checker)):
    """Readiness check endpoint - returns 200 if service is ready to accept requests"""
    try:
        readiness_status = await health_checker.check_readiness()
        return JSONResponse(
            status_code=200 if readiness_status["ready"] else 503,
            content=readiness_status
        )
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={"ready": False, "error": str(e)}
        )


@app.post("/extract")
async def extract_document(
    file_content: bytes = None,
    filename: str = None,
    mime_type: str = None,
    logger = Depends(get_logger),
    health_checker: HealthChecker = Depends(get_health_checker),
    processor_registry: ProcessorRegistry = Depends(get_processor_registry)
):
    """Extract structured data from documents (email, PDF, Word, Excel, CSV)"""
    logger.info("Document extraction endpoint called", extra={
        "input_filename": filename,
        "input_mime_type": mime_type,
        "has_content": bool(file_content)
    })
    
    # Check if service is ready
    readiness_status = await health_checker.check_readiness()
    if not readiness_status["ready"]:
        raise HTTPException(
            status_code=503,
            detail="Service not ready for processing"
        )
    
    # For now, return basic information about supported processors
    if not file_content and not filename:
        return {
            "message": "Document extraction service ready",
            "supported_types": processor_registry.get_supported_types(),
            "processors": processor_registry.get_processor_info()
        }
    
    # TODO: Implement actual file processing after OCR & Image Processing (Task 3.3)
    # This will be implemented after completing:
    # - Task 3.3: OCR & Image Processing
    # - Task 3.4: Table Extraction  
    # - Task 3.5: Deterministic Extraction
    
    return {
        "message": "Document processing implementation coming soon - completing OCR setup first",
        "received": {
            "input_filename": filename,
            "mime_type": mime_type,
            "content_size": len(file_content) if file_content else 0
        }
    }


@app.get("/processors")
async def list_processors(
    processor_registry: ProcessorRegistry = Depends(get_processor_registry)
):
    """List available document processors and their capabilities"""
    return {
        "processors": processor_registry.get_processor_info(),
        "supported_types": processor_registry.get_supported_types()
    }


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler for unhandled errors"""
    logger = logging.getLogger(__name__)
    logger.error(f"Unhandled exception: {exc}", extra={
        "path": request.url.path,
        "method": request.method,
        "error_type": type(exc).__name__
    })
    
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error"}
    )


def main():
    """Main entry point"""
    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
        access_log=True
    )


if __name__ == "__main__":
    main()