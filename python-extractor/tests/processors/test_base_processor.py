"""
Tests for base processor functionality
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.processors.base_processor import BaseProcessor, ProcessingResult, ProcessingContext


class TestProcessingResult:
    """Test ProcessingResult dataclass"""
    
    def test_successful_result(self):
        result = ProcessingResult(
            success=True,
            elements=[{"type": "Text", "text": "test"}],
            metadata={"test": "data"}
        )
        
        assert result.success is True
        assert len(result.elements) == 1
        assert result.elements[0]["text"] == "test"
        assert result.metadata["test"] == "data"
        assert result.error is None
    
    def test_error_result(self):
        result = ProcessingResult(
            success=False,
            elements=[],
            metadata={},
            error="Processing failed"
        )
        
        assert result.success is False
        assert len(result.elements) == 0
        assert result.error == "Processing failed"


class TestProcessingContext:
    """Test ProcessingContext dataclass"""
    
    def test_context_creation(self):
        context = ProcessingContext(
            filename="test.txt",
            mime_type="text/plain",
            options={"key": "value"}
        )
        
        assert context.filename == "test.txt"
        assert context.mime_type == "text/plain"
        assert context.options["key"] == "value"
        assert context.file_path is None
        assert context.file_content is None


class ConcreteProcessor(BaseProcessor):
    """Concrete implementation of BaseProcessor for testing"""
    
    def can_process(self, context: ProcessingContext) -> bool:
        return context.filename and context.filename.endswith('.txt')
    
    async def process(self, context: ProcessingContext) -> ProcessingResult:
        if not self.can_process(context):
            return self._create_error_result("Cannot process file")
        
        elements = [{"type": "Text", "text": "processed content"}]
        return self._create_success_result(elements, {"processed": True})


class TestBaseProcessor:
    """Test BaseProcessor abstract functionality"""
    
    def test_concrete_processor_creation(self):
        processor = ConcreteProcessor()
        assert processor is not None
        assert hasattr(processor, 'logger')
    
    def test_can_process(self):
        processor = ConcreteProcessor()
        
        # Test valid context
        context = ProcessingContext(filename="test.txt")
        assert processor.can_process(context) is True
        
        # Test invalid context
        context = ProcessingContext(filename="test.pdf")
        assert processor.can_process(context) is False
    
    @pytest.mark.asyncio
    async def test_process_success(self):
        processor = ConcreteProcessor()
        context = ProcessingContext(filename="test.txt")
        
        result = await processor.process(context)
        
        assert result.success is True
        assert len(result.elements) == 1
        assert result.elements[0]["text"] == "processed content"
        assert result.metadata["processed"] is True
    
    @pytest.mark.asyncio
    async def test_process_error(self):
        processor = ConcreteProcessor()
        context = ProcessingContext(filename="test.pdf")  # Unsupported file
        
        result = await processor.process(context)
        
        assert result.success is False
        assert len(result.elements) == 0
        assert "Cannot process file" in result.error
    
    def test_create_success_result(self):
        processor = ConcreteProcessor()
        elements = [{"type": "Text", "text": "test"}]
        metadata = {"key": "value"}
        
        result = processor._create_success_result(elements, metadata, 150.5)
        
        assert result.success is True
        assert result.elements == elements
        assert result.metadata == metadata
        assert result.processing_time_ms == 150.5
        assert result.error is None
    
    def test_create_error_result(self):
        processor = ConcreteProcessor()
        error_message = "Processing failed"
        
        result = processor._create_error_result(error_message)
        
        assert result.success is False
        assert result.elements == []
        assert result.metadata == {}
        assert result.error == error_message
        assert result.processing_time_ms is None
    
    def test_sanitize_text(self):
        processor = ConcreteProcessor()
        
        # Test normal text
        assert processor._sanitize_text("Hello world") == "Hello world"
        
        # Test text with extra whitespace
        assert processor._sanitize_text("  Hello   world  ") == "Hello world"
        
        # Test text with control characters
        assert processor._sanitize_text("Hello\x00world\x01") == "Helloworld"
        
        # Test text with newlines and tabs (gets normalized to single spaces)
        assert processor._sanitize_text("Hello\nworld\t") == "Hello world"
        
        # Test empty text
        assert processor._sanitize_text("") == ""
        assert processor._sanitize_text(None) == ""
    
    def test_extract_metadata(self):
        processor = ConcreteProcessor()
        
        # Mock element with metadata attribute
        class MockElement:
            def __init__(self, metadata_dict):
                self.metadata = MockMetadata(metadata_dict)
        
        class MockMetadata:
            def __init__(self, data):
                self.data = data
            
            def to_dict(self):
                return self.data
        
        element = MockElement({"key": "value", "category": "Text"})
        metadata = processor._extract_metadata(element)
        
        assert metadata["key"] == "value"
        assert metadata["category"] == "Text"
        
        # Test dict element
        element_dict = {"metadata": {"key2": "value2"}}
        metadata = processor._extract_metadata(element_dict)
        
        assert metadata["key2"] == "value2"
        
        # Test element without metadata
        element_no_metadata = {}
        metadata = processor._extract_metadata(element_no_metadata)
        
        assert metadata == {}