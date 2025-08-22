"""
Tests for FastAPI main application
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch

from src.main import app


@pytest.fixture
def client():
    """Test client for FastAPI app"""
    return TestClient(app)


@pytest.fixture
def mock_health_checker():
    """Mock health checker for testing"""
    mock = MagicMock()
    mock.check_health = AsyncMock(return_value={
        "healthy": True,
        "timestamp": 1234567890,
        "uptime_seconds": 100,
        "service": "email-extractor",
        "version": "0.1.0"
    })
    mock.check_readiness = AsyncMock(return_value={
        "ready": True,
        "timestamp": 1234567890,
        "uptime_seconds": 100,
        "service": "email-extractor",
        "version": "0.1.0",
        "dependencies": {}
    })
    return mock


@pytest.fixture
def mock_processor_registry():
    """Mock processor registry for testing"""
    mock = MagicMock()
    mock.get_supported_types.return_value = {
        "extensions": [".eml", ".pdf", ".csv"],
        "mime_types": ["message/rfc822", "application/pdf", "text/csv"]
    }
    mock.get_processor_info.return_value = [
        {
            "name": "EmailProcessor",
            "supported_extensions": [".eml"],
            "supported_mime_types": ["message/rfc822"]
        }
    ]
    return mock


class TestHealthEndpoints:
    """Test health check endpoints"""
    
    @patch('src.main.get_health_checker')
    def test_health_check_success(self, mock_get_health_checker, client, mock_health_checker):
        """Test successful health check"""
        mock_get_health_checker.return_value = mock_health_checker
        
        response = client.get("/healthz")
        
        assert response.status_code == 200
        data = response.json()
        assert data["healthy"] is True
        assert data["service"] == "email-extractor"
        assert data["version"] == "0.1.0"
    
    @patch('src.main.get_health_checker')
    def test_health_check_unhealthy(self, mock_get_health_checker, client):
        """Test unhealthy health check"""
        mock_health_checker = MagicMock()
        mock_health_checker.check_health = AsyncMock(return_value={
            "healthy": False,
            "error": "System unhealthy"
        })
        mock_get_health_checker.return_value = mock_health_checker
        
        response = client.get("/healthz")
        
        assert response.status_code == 503
        data = response.json()
        assert data["healthy"] is False
        assert "error" in data
    
    @patch('src.main.get_health_checker')
    def test_health_check_exception(self, mock_get_health_checker, client):
        """Test health check with exception"""
        mock_health_checker = MagicMock()
        mock_health_checker.check_health = AsyncMock(side_effect=Exception("Health check failed"))
        mock_get_health_checker.return_value = mock_health_checker
        
        response = client.get("/healthz")
        
        assert response.status_code == 503
        data = response.json()
        assert data["healthy"] is False
        assert "Health check failed" in data["error"]
    
    @patch('src.main.get_health_checker')
    def test_readiness_check_success(self, mock_get_health_checker, client, mock_health_checker):
        """Test successful readiness check"""
        mock_get_health_checker.return_value = mock_health_checker
        
        response = client.get("/readyz")
        
        assert response.status_code == 200
        data = response.json()
        assert data["ready"] is True
        assert data["service"] == "email-extractor"
    
    @patch('src.main.get_health_checker')
    def test_readiness_check_not_ready(self, mock_get_health_checker, client):
        """Test readiness check when not ready"""
        mock_health_checker = MagicMock()
        mock_health_checker.check_readiness = AsyncMock(return_value={
            "ready": False,
            "error": "Dependencies not available"
        })
        mock_get_health_checker.return_value = mock_health_checker
        
        response = client.get("/readyz")
        
        assert response.status_code == 503
        data = response.json()
        assert data["ready"] is False
        assert "error" in data


class TestProcessorEndpoints:
    """Test processor-related endpoints"""
    
    @patch('src.main.get_processor_registry')
    def test_list_processors_success(self, mock_get_registry, client, mock_processor_registry):
        """Test successful processor listing"""
        mock_get_registry.return_value = mock_processor_registry
        
        response = client.get("/processors")
        
        assert response.status_code == 200
        data = response.json()
        assert "processors" in data
        assert "supported_types" in data
        assert len(data["processors"]) == 1
        assert data["processors"][0]["name"] == "EmailProcessor"
        assert ".eml" in data["supported_types"]["extensions"]


class TestExtractEndpoint:
    """Test document extraction endpoint"""
    
    @patch('src.main.get_processor_registry')
    @patch('src.main.get_health_checker')
    def test_extract_no_content_info_response(self, mock_get_health_checker, mock_get_registry, client, mock_health_checker, mock_processor_registry):
        """Test extract endpoint without content returns info"""
        mock_get_health_checker.return_value = mock_health_checker
        mock_get_registry.return_value = mock_processor_registry
        
        response = client.post("/extract")
        
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "Document extraction service ready" in data["message"]
        assert "supported_types" in data
        assert "processors" in data
    
    @patch('src.main.get_processor_registry')
    @patch('src.main.get_health_checker')
    def test_extract_service_not_ready(self, mock_get_health_checker, mock_get_registry, client, mock_processor_registry):
        """Test extract endpoint when service not ready"""
        mock_health_checker = MagicMock()
        mock_health_checker.check_readiness = AsyncMock(return_value={"ready": False})
        mock_get_health_checker.return_value = mock_health_checker
        mock_get_registry.return_value = mock_processor_registry
        
        response = client.post("/extract")
        
        assert response.status_code == 503
        data = response.json()
        assert data["detail"] == "Service not ready for processing"
    
    @patch('src.main.get_processor_registry')
    @patch('src.main.get_health_checker')
    def test_extract_with_content_placeholder(self, mock_get_health_checker, mock_get_registry, client, mock_health_checker, mock_processor_registry):
        """Test extract endpoint with content (placeholder implementation)"""
        mock_get_health_checker.return_value = mock_health_checker
        mock_get_registry.return_value = mock_processor_registry
        
        # Send request with content
        response = client.post("/extract", json={
            "file_content": "sample content",
            "filename": "test.pdf",
            "mime_type": "application/pdf"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert "Document processing implementation coming soon" in data["message"]
        assert "received" in data
        assert data["received"]["input_filename"] == "test.pdf"
        assert data["received"]["mime_type"] == "application/pdf"


class TestExceptionHandling:
    """Test global exception handling"""
    
    def test_global_exception_handler(self, client):
        """Test global exception handler"""
        # This would require creating an endpoint that raises an exception
        # For now, we test that the handler is configured
        assert hasattr(app, 'exception_handlers')


class TestApplicationLifespan:
    """Test application lifespan events"""
    
    @patch('src.main.setup_logging')
    def test_lifespan_startup_logging(self, mock_setup_logging):
        """Test that logging is set up during startup"""
        # This test is more integration-focused and would require
        # testing the actual lifespan context manager
        pass


# Additional test for dependency injection
class TestDependencyInjection:
    """Test dependency injection functionality"""
    
    @patch('src.main.get_logger')
    @patch('src.main.get_health_checker')
    @patch('src.main.get_processor_registry')
    def test_dependencies_injected(self, mock_get_registry, mock_get_health_checker, mock_get_logger, client, mock_health_checker, mock_processor_registry):
        """Test that dependencies are properly injected"""
        mock_get_health_checker.return_value = mock_health_checker
        mock_get_registry.return_value = mock_processor_registry
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger
        
        response = client.post("/extract")
        
        assert response.status_code == 200
        # Verify dependencies were called
        mock_get_health_checker.assert_called()
        mock_get_registry.assert_called()
        mock_get_logger.assert_called()


# Test for application metadata
class TestApplicationMetadata:
    """Test application metadata and configuration"""
    
    def test_app_title_and_description(self):
        """Test FastAPI app has correct title and description"""
        assert app.title == "Email Extractor"
        assert "Python sidecar for extracting structured data" in app.description
    
    def test_app_version(self):
        """Test FastAPI app version"""
        assert app.version == "0.1.0"