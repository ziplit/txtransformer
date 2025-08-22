"""
Tests for processor registry
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.processor_registry import ProcessorRegistry
from src.processors.base_processor import BaseProcessor, ProcessingContext, ProcessingResult


class MockProcessor(BaseProcessor):
    """Mock processor for testing"""
    
    SUPPORTED_EXTENSIONS = {'.test'}
    SUPPORTED_MIME_TYPES = {'test/mock'}
    
    def __init__(self, name="MockProcessor", can_process_result=True):
        super().__init__()
        self.name = name
        self._can_process_result = can_process_result
        self.process_called = False
    
    def can_process(self, context: ProcessingContext) -> bool:
        return self._can_process_result
    
    async def process(self, context: ProcessingContext) -> ProcessingResult:
        self.process_called = True
        if self._can_process_result:
            return self._create_success_result(
                elements=[{"type": "Text", "text": f"Processed by {self.name}"}],
                metadata={"processor": self.name}
            )
        else:
            return self._create_error_result(f"{self.name} cannot process")


class TestProcessorRegistry:
    """Test ProcessorRegistry functionality"""
    
    def test_registry_initialization(self):
        """Test registry initialization with default processors"""
        registry = ProcessorRegistry()
        
        assert len(registry.processors) == 3  # Email, PDF, Document
        
        # Check that default processors are registered
        processor_names = [type(p).__name__ for p in registry.processors]
        assert "EmailProcessor" in processor_names
        assert "PDFProcessor" in processor_names
        assert "DocumentProcessor" in processor_names
    
    def test_register_custom_processor(self):
        """Test registering custom processors"""
        registry = ProcessorRegistry()
        initial_count = len(registry.processors)
        
        custom_processor = MockProcessor("CustomProcessor")
        registry.register_processor(custom_processor)
        
        assert len(registry.processors) == initial_count + 1
        assert custom_processor in registry.processors
    
    def test_get_processor_success(self):
        """Test getting appropriate processor for context"""
        registry = ProcessorRegistry()
        
        # Test email processor selection
        context = ProcessingContext(filename="test.eml")
        processor = registry.get_processor(context)
        
        assert processor is not None
        assert type(processor).__name__ == "EmailProcessor"
    
    def test_get_processor_no_match(self):
        """Test getting processor when no processor can handle the context"""
        registry = ProcessorRegistry()
        
        # Use unsupported file type
        context = ProcessingContext(filename="test.unsupported")
        processor = registry.get_processor(context)
        
        assert processor is None
    
    def test_get_processor_first_match(self):
        """Test that first matching processor is returned"""
        registry = ProcessorRegistry()
        
        # Add two mock processors that can both process the same context
        mock1 = MockProcessor("FirstMock", can_process_result=True)
        mock2 = MockProcessor("SecondMock", can_process_result=True)
        
        registry.register_processor(mock1)
        registry.register_processor(mock2)
        
        context = ProcessingContext(filename="test.test")  # Both can process .test files
        processor = registry.get_processor(context)
        
        # Should return the first one registered (mock1)
        assert processor == mock1
    
    @pytest.mark.asyncio
    async def test_process_document_success(self):
        """Test successful document processing through registry"""
        registry = ProcessorRegistry()
        custom_processor = MockProcessor("TestProcessor")
        registry.register_processor(custom_processor)
        
        context = ProcessingContext(filename="test.test")
        result = await registry.process_document(context)
        
        assert result.success is True
        assert result.elements[0]["text"] == "Processed by TestProcessor"
        assert result.metadata["selected_processor"] == "MockProcessor"
        assert custom_processor.process_called is True
    
    @pytest.mark.asyncio
    async def test_process_document_no_processor(self):
        """Test document processing when no processor available"""
        registry = ProcessorRegistry()
        
        context = ProcessingContext(filename="test.unsupported")
        result = await registry.process_document(context)
        
        assert result.success is False
        assert "No processor available" in result.error
        assert result.metadata == {}
    
    @pytest.mark.asyncio
    async def test_process_document_processor_error(self):
        """Test document processing when processor raises exception"""
        registry = ProcessorRegistry()
        
        # Create processor that will raise exception
        error_processor = MockProcessor("ErrorProcessor")
        
        # Mock the process method to raise exception
        async def mock_process(context):
            raise Exception("Processing failed")
        
        error_processor.process = mock_process
        registry.register_processor(error_processor)
        
        context = ProcessingContext(filename="test.test")
        result = await registry.process_document(context)
        
        assert result.success is False
        assert "Processing failed with MockProcessor" in result.error
        assert result.metadata["selected_processor"] == "MockProcessor"
    
    def test_get_supported_types(self):
        """Test getting all supported types from all processors"""
        registry = ProcessorRegistry()
        
        supported = registry.get_supported_types()
        
        assert "extensions" in supported
        assert "mime_types" in supported
        assert isinstance(supported["extensions"], list)
        assert isinstance(supported["mime_types"], list)
        
        # Check some expected types are present
        assert ".eml" in supported["extensions"]
        assert ".pdf" in supported["extensions"]
        assert ".csv" in supported["extensions"]
        assert "message/rfc822" in supported["mime_types"]
        assert "application/pdf" in supported["mime_types"]
        assert "text/csv" in supported["mime_types"]
        
        # Check lists are sorted and deduplicated
        assert supported["extensions"] == sorted(supported["extensions"])
        assert supported["mime_types"] == sorted(supported["mime_types"])
        assert len(supported["extensions"]) == len(set(supported["extensions"]))
    
    def test_get_supported_types_with_custom_processor(self):
        """Test supported types includes custom processor types"""
        registry = ProcessorRegistry()
        custom_processor = MockProcessor("CustomProcessor")
        registry.register_processor(custom_processor)
        
        supported = registry.get_supported_types()
        
        assert ".test" in supported["extensions"]
        assert "test/mock" in supported["mime_types"]
    
    def test_get_processor_info(self):
        """Test getting information about all processors"""
        registry = ProcessorRegistry()
        
        info = registry.get_processor_info()
        
        assert len(info) == 3  # Default processors
        assert isinstance(info, list)
        
        # Check structure of processor info
        for processor_info in info:
            assert "name" in processor_info
            assert "supported_extensions" in processor_info
            assert "supported_mime_types" in processor_info
            assert isinstance(processor_info["name"], str)
        
        # Check specific processors are present
        processor_names = [p["name"] for p in info]
        assert "EmailProcessor" in processor_names
        assert "PDFProcessor" in processor_names
        assert "DocumentProcessor" in processor_names
    
    def test_get_processor_info_with_custom_processor(self):
        """Test processor info includes custom processors"""
        registry = ProcessorRegistry()
        custom_processor = MockProcessor("CustomProcessor")
        registry.register_processor(custom_processor)
        
        info = registry.get_processor_info()
        
        assert len(info) == 4  # 3 default + 1 custom
        custom_info = next((p for p in info if p["name"] == "MockProcessor"), None)
        assert custom_info is not None
        assert custom_info["supported_extensions"] == {'.test'}
        assert custom_info["supported_mime_types"] == {'test/mock'}
    
    def test_processor_without_supported_types(self):
        """Test processor without SUPPORTED_* attributes"""
        registry = ProcessorRegistry()
        
        class MinimalProcessor(BaseProcessor):
            def can_process(self, context):
                return False
            
            async def process(self, context):
                return self._create_error_result("Not implemented")
        
        minimal_processor = MinimalProcessor()
        registry.register_processor(minimal_processor)
        
        info = registry.get_processor_info()
        minimal_info = next((p for p in info if p["name"] == "MinimalProcessor"), None)
        assert minimal_info is not None
        assert minimal_info["supported_extensions"] == set()
        assert minimal_info["supported_mime_types"] == set()
    
    def test_processor_selection_priority(self):
        """Test that processors are checked in registration order"""
        registry = ProcessorRegistry()
        
        # Clear default processors for this test
        registry.processors = []
        
        # Add processors in specific order
        processor1 = MockProcessor("First", can_process_result=True)
        processor2 = MockProcessor("Second", can_process_result=True)
        processor3 = MockProcessor("Third", can_process_result=False)
        
        registry.register_processor(processor1)
        registry.register_processor(processor2)
        registry.register_processor(processor3)
        
        context = ProcessingContext(filename="test.test")
        selected = registry.get_processor(context)
        
        # Should select first processor that can process
        assert selected == processor1
    
    @pytest.mark.asyncio
    async def test_process_document_metadata_injection(self):
        """Test that processor registry injects metadata about selected processor"""
        registry = ProcessorRegistry()
        custom_processor = MockProcessor("MetadataTest")
        registry.register_processor(custom_processor)
        
        context = ProcessingContext(filename="test.test")
        result = await registry.process_document(context)
        
        assert result.success is True
        assert "selected_processor" in result.metadata
        assert result.metadata["selected_processor"] == "MockProcessor"
        # Original processor metadata should also be preserved
        assert result.metadata["processor"] == "MetadataTest"