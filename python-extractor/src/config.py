"""
Configuration management for the email extractor service.
"""

import os
from typing import List, Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings with environment variable support."""
    
    # Server configuration
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    
    # Processing configuration
    max_file_size: int = 50 * 1024 * 1024  # 50MB
    temp_dir: str = "/tmp/extractor"
    
    # OCR configuration
    tesseract_cmd: Optional[str] = None
    ocr_enabled: bool = True
    ocr_languages: str = "eng"
    
    # spaCy configuration
    spacy_model: str = "en_core_web_sm"
    
    # Timeouts
    processing_timeout: int = 300  # 5 minutes
    
    # Logging
    log_level: str = "INFO"
    log_format: str = "json"
    
    # Health check configuration
    health_check_timeout: float = 1.0
    readiness_check_timeout: float = 5.0
    
    class Config:
        env_prefix = "EXTRACTOR_"
        case_sensitive = False


# Global settings instance
settings = Settings()