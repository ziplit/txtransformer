"""
Logging configuration for the Email Extractor service
"""

import json
import logging
import sys
from datetime import datetime
from typing import Any, Dict

from .config import settings


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging"""
    
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": "email-extractor",
            "version": "0.1.0"
        }
        
        # Add extra fields from record
        if hasattr(record, 'extra') and record.extra:
            log_data.update(record.extra)
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        # Add stack info if present
        if record.stack_info:
            log_data["stack_info"] = record.stack_info
            
        return json.dumps(log_data, separators=(',', ':'))


class PlainFormatter(logging.Formatter):
    """Plain text formatter for development"""
    
    def __init__(self):
        super().__init__(
            fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )


def setup_logging():
    """Configure logging based on settings"""
    
    # Clear any existing handlers
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Create handler
    handler = logging.StreamHandler(sys.stdout)
    
    # Set formatter based on configuration
    if settings.log_format.lower() == "json":
        formatter = JSONFormatter()
    else:
        formatter = PlainFormatter()
    
    handler.setFormatter(formatter)
    
    # Set log level
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)
    handler.setLevel(log_level)
    
    # Configure root logger
    root_logger.setLevel(log_level)
    root_logger.addHandler(handler)
    
    # Configure uvicorn loggers
    for logger_name in ["uvicorn", "uvicorn.access", "uvicorn.error"]:
        logger = logging.getLogger(logger_name)
        logger.handlers = []
        logger.addHandler(handler)
        logger.setLevel(log_level)
        logger.propagate = False


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the given name"""
    return logging.getLogger(name)


def sanitize_log_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Sanitize log data to remove sensitive information"""
    sensitive_keys = {
        'password', 'token', 'key', 'secret', 'authorization',
        'auth', 'credential', 'api_key', 'access_token'
    }
    
    def _sanitize_value(key: str, value: Any) -> Any:
        if isinstance(key, str) and any(sensitive in key.lower() for sensitive in sensitive_keys):
            return "[REDACTED]"
        
        if isinstance(value, dict):
            return {k: _sanitize_value(k, v) for k, v in value.items()}
        elif isinstance(value, list):
            return [_sanitize_value(str(i), item) for i, item in enumerate(value)]
        else:
            return value
    
    return {k: _sanitize_value(k, v) for k, v in data.items()}