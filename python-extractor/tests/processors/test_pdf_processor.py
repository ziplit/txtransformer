"""
Tests for PDF processor
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

from src.processors.pdf_processor import PDFProcessor
from src.processors.base_processor import ProcessingContext


class TestPDFProcessor:
    """Test PDFProcessor functionality"""
    
    @pytest.fixture
    def processor(self):
        return PDFProcessor()
    
    def test_can_process_by_extension(self, processor):
        """Test processor selection by file extension"""
        # Test .pdf file
        context = ProcessingContext(filename="test.pdf")
        assert processor.can_process(context) is True
        
        # Test case insensitive
        context = ProcessingContext(filename="test.PDF")
        assert processor.can_process(context) is True
        
        # Test unsupported extension
        context = ProcessingContext(filename="test.docx")
        assert processor.can_process(context) is False
    
    def test_can_process_by_path(self, processor):
        """Test processor selection by file path"""
        context = ProcessingContext(file_path=Path("document.pdf"))
        assert processor.can_process(context) is True
        
        context = ProcessingContext(file_path=Path("document.txt"))
        assert processor.can_process(context) is False
    
    def test_can_process_by_mime_type(self, processor):
        """Test processor selection by MIME type"""
        context = ProcessingContext(mime_type="application/pdf")
        assert processor.can_process(context) is True
        
        context = ProcessingContext(mime_type="text/plain")
        assert processor.can_process(context) is False
    
    @pytest.mark.asyncio
    @patch('src.processors.pdf_processor.partition_pdf')
    async def test_process_success_with_file_path(self, mock_partition, processor, processing_context_pdf):
        """Test successful PDF processing from file path"""
        # Mock elements including a table
        mock_elements = [
            MagicMock(spec=['metadata']),
            MagicMock(spec=['metadata']),
            MagicMock(spec=['metadata'])
        ]
        
        # Text element
        mock_elements[0].__str__ = lambda: "PDF document content"
        mock_elements[0].__class__ = MagicMock(__name__="Text")
        mock_elements[0].metadata.to_dict.return_value = {
            "category": "Text",
            "page_number": 1
        }
        
        # Title element
        mock_elements[1].__str__ = lambda: "Document Title"
        mock_elements[1].__class__ = MagicMock(__name__="Title")
        mock_elements[1].metadata.to_dict.return_value = {
            "category": "Title",
            "page_number": 1,
            "coordinates": {"x": 100, "y": 200}
        }
        
        # Table element
        mock_elements[2].__str__ = lambda: "Table data here"
        mock_elements[2].__class__ = MagicMock(__name__="Table")
        mock_elements[2].metadata.to_dict.return_value = {
            "category": "Table",
            "page_number": 1,
            "text_as_html": "<table><tr><td>Data</td></tr></table>"
        }
        
        mock_partition.return_value = mock_elements
        
        result = await processor.process(processing_context_pdf)
        
        assert result.success is True
        assert len(result.elements) == 3
        assert result.metadata["processor"] == "pdf"
        assert result.metadata["tables_count"] == 1
        assert len(result.metadata["tables"]) == 1
        
        # Check table extraction
        table = result.metadata["tables"][0]
        assert table["type"] == "table"
        assert table["content"] == "Table data here"
        assert table["html"] == "<table><tr><td>Data</td></tr></table>"
        assert table["page_number"] == 1
        
        # Verify partition_pdf was called with correct parameters
        mock_partition.assert_called_once()
        call_args = mock_partition.call_args[1]
        assert call_args["strategy"] == "hi_res"
        assert call_args["infer_table_structure"] is True
        assert call_args["extract_images_in_pdf"] is False
        assert call_args["include_page_breaks"] is True
    
    @pytest.mark.asyncio
    @patch('src.processors.pdf_processor.partition_pdf')
    @patch('tempfile.NamedTemporaryFile')
    @patch('os.unlink')
    async def test_process_with_content_bytes(self, mock_unlink, mock_tempfile, mock_partition, processor, sample_pdf_content):
        """Test PDF processing from content bytes using temp file"""
        mock_temp = MagicMock()
        mock_temp.name = "/tmp/test.pdf"
        mock_tempfile.return_value.__enter__.return_value = mock_temp
        
        mock_elements = [MagicMock(spec=['metadata'])]
        mock_elements[0].__str__ = lambda: "PDF content from bytes"
        mock_elements[0].__class__ = MagicMock(__name__="Text")
        mock_elements[0].metadata.to_dict.return_value = {"category": "Text"}
        
        mock_partition.return_value = mock_elements
        
        context = ProcessingContext(
            file_content=sample_pdf_content,
            filename="test.pdf",
            mime_type="application/pdf"
        )
        
        result = await processor.process(context)
        
        assert result.success is True
        mock_temp.write.assert_called_once_with(sample_pdf_content)
        mock_partition.assert_called_once_with(filename="/tmp/test.pdf", strategy="hi_res", infer_table_structure=True, extract_images_in_pdf=False, include_page_breaks=True)
        mock_unlink.assert_called_once_with("/tmp/test.pdf")
    
    @pytest.mark.asyncio
    @patch('src.processors.pdf_processor.partition_pdf')
    async def test_process_with_ocr_enabled(self, mock_partition, processor, processing_context_pdf):
        """Test PDF processing with OCR enabled"""
        mock_partition.return_value = []
        
        # Mock settings to enable OCR
        with patch('src.processors.pdf_processor.settings') as mock_settings:
            mock_settings.ocr_enabled = True
            mock_settings.ocr_languages = "eng+fra"
            
            await processor.process(processing_context_pdf)
            
            call_args = mock_partition.call_args[1]
            assert "languages" in call_args
            assert call_args["languages"] == ["eng+fra"]
            assert call_args["ocr_languages"] == "eng+fra"
    
    @pytest.mark.asyncio
    async def test_process_error_no_content(self, processor):
        """Test error handling when no content provided"""
        context = ProcessingContext(filename="test.pdf")
        
        result = await processor.process(context)
        
        assert result.success is False
        assert "PDF processing failed" in result.error
        assert "No valid PDF content provided" in result.error
    
    @pytest.mark.asyncio
    @patch('src.processors.pdf_processor.partition_pdf')
    async def test_process_error_partition_failure(self, mock_partition, processor, processing_context_pdf):
        """Test error handling when partition_pdf fails"""
        mock_partition.side_effect = Exception("PDF parsing failed")
        
        result = await processor.process(processing_context_pdf)
        
        assert result.success is False
        assert "PDF processing failed" in result.error
        assert "PDF parsing failed" in result.error
    
    def test_extract_tables(self, processor):
        """Test table extraction from elements"""
        mock_elements = [
            MagicMock(spec=['metadata']),
            MagicMock(spec=['metadata']),
            MagicMock(spec=['metadata'])
        ]
        
        # Text element (not a table)
        mock_elements[0].__class__ = MagicMock(__name__="Text")
        
        # Table element
        mock_elements[1].__str__ = lambda: "Table content here"
        mock_elements[1].__class__ = MagicMock(__name__="Table")
        mock_elements[1].metadata.to_dict.return_value = {
            "text_as_html": "<table><tr><td>Cell 1</td><td>Cell 2</td></tr></table>",
            "page_number": 2
        }
        
        # Another table element
        mock_elements[2].__str__ = lambda: "Another table"
        mock_elements[2].__class__ = MagicMock(__name__="Table")
        mock_elements[2].metadata.to_dict.return_value = {
            "page_number": 3
        }
        
        tables = processor._extract_tables(mock_elements)
        
        assert len(tables) == 2
        assert tables[0]["content"] == "Table content here"
        assert tables[0]["type"] == "table"
        assert tables[0]["html"] == "<table><tr><td>Cell 1</td><td>Cell 2</td></tr></table>"
        assert tables[0]["page_number"] == 2
        
        assert tables[1]["content"] == "Another table"
        assert tables[1]["page_number"] == 3
    
    @pytest.mark.asyncio
    @patch('src.processors.pdf_processor.partition_pdf')
    async def test_extract_text_only(self, mock_partition, processor, processing_context_pdf):
        """Test text-only extraction mode"""
        mock_elements = [
            MagicMock(spec=['metadata']),
            MagicMock(spec=['metadata'])
        ]
        
        mock_elements[0].__str__ = lambda: "First paragraph"
        mock_elements[0].__class__ = MagicMock(__name__="Text")
        mock_elements[0].metadata.to_dict.return_value = {"page_number": 1}
        
        mock_elements[1].__str__ = lambda: "Second paragraph"
        mock_elements[1].__class__ = MagicMock(__name__="Text")
        mock_elements[1].metadata.to_dict.return_value = {"page_number": 1}
        
        mock_partition.return_value = mock_elements
        
        result = await processor.extract_text_only(processing_context_pdf)
        
        assert result.success is True
        assert len(result.elements) == 2
        assert result.metadata["processor"] == "pdf_text_only"
        assert "First paragraph\nSecond paragraph" in result.metadata["full_text"]
        
        # Verify fast strategy was used
        call_args = mock_partition.call_args[1]
        assert call_args["strategy"] == "fast"
        assert call_args["infer_table_structure"] is False
    
    @pytest.mark.asyncio
    @patch('src.processors.pdf_processor.partition_pdf')
    async def test_extract_tables_only(self, mock_partition, processor, processing_context_pdf):
        """Test table-only extraction mode"""
        mock_elements = [
            MagicMock(spec=['metadata']),
            MagicMock(spec=['metadata'])
        ]
        
        # Text element (should be ignored)
        mock_elements[0].__class__ = MagicMock(__name__="Text")
        
        # Table element
        mock_elements[1].__str__ = lambda: "Table data"
        mock_elements[1].__class__ = MagicMock(__name__="Table")
        mock_elements[1].metadata.to_dict.return_value = {"page_number": 1}
        
        mock_partition.return_value = mock_elements
        
        tables = await processor.extract_tables_only(processing_context_pdf)
        
        assert len(tables) == 1
        assert tables[0]["content"] == "Table data"
        
        # Verify hi_res strategy was used for table extraction
        call_args = mock_partition.call_args[1]
        assert call_args["strategy"] == "hi_res"
        assert call_args["infer_table_structure"] is True
    
    @pytest.mark.asyncio
    @patch('src.processors.pdf_processor.partition_pdf')
    async def test_extract_tables_only_error(self, mock_partition, processor, processing_context_pdf):
        """Test error handling in table-only extraction"""
        mock_partition.side_effect = Exception("Table extraction failed")
        
        tables = await processor.extract_tables_only(processing_context_pdf)
        
        assert tables == []
    
    def test_process_elements(self, processor):
        """Test processing and structuring of elements"""
        mock_elements = [
            MagicMock(spec=['metadata']),
            MagicMock(spec=['metadata']),
            MagicMock(spec=['metadata'])
        ]
        
        # Element with full metadata
        mock_elements[0].__str__ = lambda: "Title text"
        mock_elements[0].__class__ = MagicMock(__name__="Title")
        mock_elements[0].metadata.to_dict.return_value = {
            "category": "Title",
            "page_number": 1,
            "coordinates": {"x": 100, "y": 200},
            "coordinate_system": "pixel",
            "parent_id": "parent_1"
        }
        
        # Element with minimal metadata
        mock_elements[1].__str__ = lambda: "Body text"
        mock_elements[1].__class__ = MagicMock(__name__="Text")
        mock_elements[1].metadata.to_dict.return_value = {"category": "Text"}
        
        # Element with empty text (should be filtered out)
        mock_elements[2].__str__ = lambda: ""
        mock_elements[2].__class__ = MagicMock(__name__="Text")
        mock_elements[2].metadata.to_dict.return_value = {"category": "Text"}
        
        result = processor._process_elements(mock_elements)
        
        assert len(result) == 2  # Empty element filtered out
        
        # Check first element with full metadata
        assert result[0]["type"] == "Title"
        assert result[0]["text"] == "Title text"
        assert result[0]["category"] == "Title"
        assert result[0]["page_number"] == 1
        assert result[0]["coordinates"] == {"x": 100, "y": 200}
        assert result[0]["coordinate_system"] == "pixel"
        assert result[0]["parent_id"] == "parent_1"
        
        # Check second element
        assert result[1]["type"] == "Text"
        assert result[1]["text"] == "Body text"
        assert result[1]["category"] == "Text"