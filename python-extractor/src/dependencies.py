"""
Dependency injection for the FastAPI application
"""

import logging
from typing import Generator

from .health import HealthChecker


def get_logger() -> logging.Logger:
    """Get configured logger instance"""
    return logging.getLogger(__name__)


def get_health_checker() -> HealthChecker:
    """Get health checker instance"""
    return HealthChecker()


# Global health checker instance for reuse
_health_checker = None


def get_health_checker_singleton() -> HealthChecker:
    """Get singleton health checker instance for better performance"""
    global _health_checker
    if _health_checker is None:
        _health_checker = HealthChecker()
    return _health_checker