"""
Test configuration and fixtures
"""

import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from src.processors.base_processor import ProcessingContext, ProcessingResult
from src.processor_registry import ProcessorRegistry


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_email_content():
    """Sample email content for testing"""
    return b"""From: sender@example.com
To: recipient@example.com
Subject: Test Email
Date: Mon, 1 Jan 2024 12:00:00 +0000
Message-ID: <test@example.com>

This is a test email content.

Best regards,
Test Sender
"""


@pytest.fixture
def sample_pdf_content():
    """Sample PDF content (minimal PDF structure)"""
    return b"""%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj

2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj

3 0 obj
<<
/Type /Page
/Parent 2 0 R
/MediaBox [0 0 612 792]
/Contents 4 0 R
>>
endobj

4 0 obj
<<
/Length 44
>>
stream
BT
/F1 12 Tf
100 700 Td
(Test PDF Content) Tj
ET
endstream
endobj

xref
0 5
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000206 00000 n 
trailer
<<
/Size 5
/Root 1 0 R
>>
startxref
300
%%EOF"""


@pytest.fixture
def sample_csv_content():
    """Sample CSV content for testing"""
    return b"""name,email,age
John Doe,john@example.com,30
Jane Smith,jane@example.com,25
Bob Johnson,bob@example.com,35
"""


@pytest.fixture
def processing_context_email(sample_email_content, temp_dir):
    """Processing context for email testing"""
    email_file = temp_dir / "test_email.eml"
    email_file.write_bytes(sample_email_content)
    
    return ProcessingContext(
        file_path=email_file,
        file_content=sample_email_content,
        filename="test_email.eml",
        mime_type="message/rfc822"
    )


@pytest.fixture
def processing_context_pdf(sample_pdf_content, temp_dir):
    """Processing context for PDF testing"""
    pdf_file = temp_dir / "test_document.pdf"
    pdf_file.write_bytes(sample_pdf_content)
    
    return ProcessingContext(
        file_path=pdf_file,
        file_content=sample_pdf_content,
        filename="test_document.pdf",
        mime_type="application/pdf"
    )


@pytest.fixture
def processing_context_csv(sample_csv_content, temp_dir):
    """Processing context for CSV testing"""
    csv_file = temp_dir / "test_data.csv"
    csv_file.write_bytes(sample_csv_content)
    
    return ProcessingContext(
        file_path=csv_file,
        file_content=sample_csv_content,
        filename="test_data.csv",
        mime_type="text/csv"
    )


@pytest.fixture
def mock_unstructured_elements():
    """Mock unstructured elements for testing"""
    class MockElement:
        def __init__(self, text, element_type="Text", metadata=None):
            self.text = text
            self.element_type = element_type
            self.metadata = MockMetadata(metadata or {})
        
        def __str__(self):
            return self.text
        
        def __class__(self):
            class MockClass:
                __name__ = self.element_type
            return MockClass
        
        def __type__(self):
            class MockType:
                __name__ = self.element_type
            return MockType()
    
    class MockMetadata:
        def __init__(self, data):
            self.data = data
        
        def to_dict(self):
            return self.data
    
    return [
        MockElement("Test email subject", "Title", {"category": "Title"}),
        MockElement("Test email body content", "Text", {"category": "Text"}),
        MockElement("Sender: sender@example.com", "Text", {"category": "Header"}),
    ]


@pytest.fixture
def processor_registry():
    """Fresh processor registry for testing"""
    return ProcessorRegistry()


@pytest.fixture
def mock_processing_result():
    """Mock processing result for testing"""
    return ProcessingResult(
        success=True,
        elements=[
            {
                "type": "Text",
                "text": "Test content",
                "metadata": {"category": "Text"}
            }
        ],
        metadata={
            "processor": "test_processor",
            "elements_count": 1
        },
        processing_time_ms=100.0
    )