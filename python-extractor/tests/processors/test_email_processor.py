"""
Tests for email processor
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

from src.processors.email_processor import EmailProcessor
from src.processors.base_processor import ProcessingContext, ProcessingResult


class TestEmailProcessor:
    """Test EmailProcessor functionality"""
    
    @pytest.fixture
    def processor(self):
        return EmailProcessor()
    
    def test_can_process_by_extension(self, processor):
        """Test processor selection by file extension"""
        # Test .eml file
        context = ProcessingContext(filename="test.eml")
        assert processor.can_process(context) is True
        
        # Test .msg file
        context = ProcessingContext(filename="test.msg")
        assert processor.can_process(context) is True
        
        # Test unsupported extension
        context = ProcessingContext(filename="test.pdf")
        assert processor.can_process(context) is False
    
    def test_can_process_by_path(self, processor):
        """Test processor selection by file path"""
        # Test .eml file path
        context = ProcessingContext(file_path=Path("test.eml"))
        assert processor.can_process(context) is True
        
        # Test .msg file path
        context = ProcessingContext(file_path=Path("test.MSG"))  # Case insensitive
        assert processor.can_process(context) is True
        
        # Test unsupported path
        context = ProcessingContext(file_path=Path("test.pdf"))
        assert processor.can_process(context) is False
    
    def test_can_process_by_mime_type(self, processor):
        """Test processor selection by MIME type"""
        # Test RFC822 MIME type
        context = ProcessingContext(mime_type="message/rfc822")
        assert processor.can_process(context) is True
        
        # Test Outlook MIME type
        context = ProcessingContext(mime_type="application/vnd.ms-outlook")
        assert processor.can_process(context) is True
        
        # Test unsupported MIME type
        context = ProcessingContext(mime_type="application/pdf")
        assert processor.can_process(context) is False
    
    def test_supported_types(self, processor):
        """Test processor supported types are correctly defined"""
        assert '.eml' in processor.SUPPORTED_EXTENSIONS
        assert '.msg' in processor.SUPPORTED_EXTENSIONS
        assert 'message/rfc822' in processor.SUPPORTED_MIME_TYPES
        assert 'application/vnd.ms-outlook' in processor.SUPPORTED_MIME_TYPES
    
    @pytest.mark.asyncio
    @patch('src.processors.email_processor.partition_email')
    async def test_process_success_with_file_path(self, mock_partition, processor, processing_context_email):
        """Test successful email processing from file path"""
        # Mock unstructured elements with proper type mocking
        from tests.test_helpers import create_mock_element
        
        mock_elements = [
            create_mock_element("Test Email Subject", "Title", {
                "category": "Title",
                "email_headers": {"Subject": "Test Email Subject"}
            }),
            create_mock_element("This is the email body content.", "Text", {
                "category": "Text", 
                "sender": "sender@example.com"
            })
        ]
        
        mock_partition.return_value = mock_elements
        
        result = await processor.process(processing_context_email)
        
        assert result.success is True
        assert len(result.elements) == 2
        assert result.elements[0]["text"] == "Test Email Subject"
        assert result.elements[0]["type"] == "Title"
        assert result.elements[0]["email_headers"]["Subject"] == "Test Email Subject"
        assert result.elements[1]["text"] == "This is the email body content."
        assert result.elements[1]["sender"] == "sender@example.com"
        assert result.metadata["processor"] == "email"
        assert result.metadata["elements_count"] == 2
        assert result.processing_time_ms is not None
        
        # Verify partition_email was called with correct parameters
        mock_partition.assert_called_once()
        call_args = mock_partition.call_args
        assert 'filename' in call_args[1]
        assert 'include_headers' in call_args[1]
        assert call_args[1]['include_headers'] is True
        assert call_args[1]['process_attachments'] is False
    
    @pytest.mark.asyncio
    @patch('src.processors.email_processor.partition_email')
    async def test_process_success_with_content(self, mock_partition, processor, sample_email_content):
        """Test successful email processing from content bytes"""
        mock_elements = [
            MagicMock(spec=['metadata'])
        ]
        
        mock_elements[0].__str__ = lambda: "Email content from bytes"
        mock_elements[0].__class__ = MagicMock(__name__="Text")
        mock_elements[0].metadata.to_dict.return_value = {"category": "Text"}
        
        mock_partition.return_value = mock_elements
        
        context = ProcessingContext(
            file_content=sample_email_content,
            filename="test.eml",
            mime_type="message/rfc822"
        )
        
        result = await processor.process(context)
        
        assert result.success is True
        assert len(result.elements) == 1
        assert result.elements[0]["text"] == "Email content from bytes"
        
        # Verify partition_email was called with content
        mock_partition.assert_called_once()
        call_args = mock_partition.call_args
        assert 'file' in call_args[1]
        assert call_args[1]['file'] == sample_email_content
    
    @pytest.mark.asyncio
    async def test_process_error_no_content(self, processor):
        """Test error handling when no content provided"""
        context = ProcessingContext(filename="test.eml")  # No file_path or file_content
        
        result = await processor.process(context)
        
        assert result.success is False
        assert "Email processing failed" in result.error
        assert len(result.elements) == 0
    
    @pytest.mark.asyncio
    @patch('src.processors.email_processor.partition_email')
    async def test_process_error_partition_failure(self, mock_partition, processor, processing_context_email):
        """Test error handling when partition_email fails"""
        mock_partition.side_effect = Exception("Partition failed")
        
        result = await processor.process(processing_context_email)
        
        assert result.success is False
        assert "Email processing failed" in result.error
        assert "Partition failed" in result.error
        assert len(result.elements) == 0
    
    def test_process_elements(self, processor):
        """Test processing of unstructured elements"""
        # Create mock elements
        mock_elements = []
        
        # Element with email headers
        elem1 = MagicMock(spec=['metadata'])
        elem1.__str__ = lambda: "Subject: Test Email"
        elem1.__class__ = MagicMock(__name__="Title")
        elem1.metadata.to_dict.return_value = {
            "category": "Title",
            "email_headers": {"Subject": "Test Email", "From": "test@example.com"},
            "sender": "test@example.com",
            "recipient": "user@example.com"
        }
        mock_elements.append(elem1)
        
        # Element with minimal metadata
        elem2 = MagicMock(spec=['metadata'])
        elem2.__str__ = lambda: "Email body content"
        elem2.__class__ = MagicMock(__name__="Text")
        elem2.metadata.to_dict.return_value = {"category": "Text"}
        mock_elements.append(elem2)
        
        # Element with empty text (should be filtered out)
        elem3 = MagicMock(spec=['metadata'])
        elem3.__str__ = lambda: "   "  # Only whitespace
        elem3.__class__ = MagicMock(__name__="Text")
        elem3.metadata.to_dict.return_value = {"category": "Text"}
        mock_elements.append(elem3)
        
        result = processor._process_elements(mock_elements)
        
        # Should only have 2 elements (empty one filtered out)
        assert len(result) == 2
        
        # Check first element
        assert result[0]["type"] == "Title"
        assert result[0]["text"] == "Subject: Test Email"
        assert result[0]["email_headers"]["Subject"] == "Test Email"
        assert result[0]["sender"] == "test@example.com"
        assert result[0]["recipient"] == "user@example.com"
        assert result[0]["category"] == "Title"
        
        # Check second element
        assert result[1]["type"] == "Text"
        assert result[1]["text"] == "Email body content"
        assert result[1]["category"] == "Text"
    
    @pytest.mark.asyncio
    @patch('src.processors.email_processor.partition_email')
    async def test_extract_headers(self, mock_partition, processor, processing_context_email):
        """Test header extraction functionality"""
        mock_elements = [MagicMock(spec=['metadata'])]
        mock_elements[0].metadata.to_dict.return_value = {
            "email_headers": {
                "Subject": "Test Subject",
                "From": "sender@example.com",
                "To": "recipient@example.com",
                "Date": "Mon, 1 Jan 2024 12:00:00 +0000"
            }
        }
        mock_partition.return_value = mock_elements
        
        headers = await processor.extract_headers(processing_context_email)
        
        assert headers["Subject"] == "Test Subject"
        assert headers["From"] == "sender@example.com"
        assert headers["To"] == "recipient@example.com"
        assert headers["Date"] == "Mon, 1 Jan 2024 12:00:00 +0000"
    
    @pytest.mark.asyncio
    @patch('src.processors.email_processor.partition_email')
    async def test_extract_headers_error(self, mock_partition, processor, processing_context_email):
        """Test header extraction error handling"""
        mock_partition.side_effect = Exception("Header extraction failed")
        
        headers = await processor.extract_headers(processing_context_email)
        
        assert headers == {}
    
    @pytest.mark.asyncio
    @patch('src.processors.email_processor.partition_email')
    async def test_extract_attachments_info(self, mock_partition, processor, processing_context_email):
        """Test attachment information extraction"""
        mock_elements = [MagicMock(spec=['metadata'])]
        mock_elements[0].metadata.to_dict.return_value = {
            "attached_to_filename": "attachment.pdf",
            "file_directory": "application/pdf",
            "file_size": 1024
        }
        mock_partition.return_value = mock_elements
        
        attachments = await processor.extract_attachments_info(processing_context_email)
        
        assert len(attachments) == 1
        assert attachments[0]["filename"] == "attachment.pdf"
        assert attachments[0]["content_type"] == "application/pdf"
        assert attachments[0]["size"] == 1024
    
    @pytest.mark.asyncio
    @patch('src.processors.email_processor.partition_email')
    async def test_process_with_options(self, mock_partition, processor, processing_context_email):
        """Test processing with custom options"""
        mock_partition.return_value = []
        
        # Add custom options to context
        processing_context_email.options = {
            "process_attachments": True,
            "custom_option": "value"
        }
        
        await processor.process(processing_context_email)
        
        # Verify options were passed to partition_email
        call_args = mock_partition.call_args[1]
        assert call_args["process_attachments"] is True
        assert call_args["custom_option"] == "value"
        assert call_args["include_headers"] is True  # Default option preserved