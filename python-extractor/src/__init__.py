"""
Email Extractor - Python sidecar for processing emails and attachments
"""

__version__ = "0.1.0"
__author__ = "Email Transformer Library"
__description__ = "Python sidecar for extracting structured data from emails and attachments"

from .main import app
from .config import settings
from .health import HealthChecker

__all__ = ["app", "settings", "HealthChecker"]