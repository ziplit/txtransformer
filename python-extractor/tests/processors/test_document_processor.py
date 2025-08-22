"""
Tests for document processor (Word, Excel, CSV)
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

from src.processors.document_processor import DocumentProcessor
from src.processors.base_processor import ProcessingContext


class TestDocumentProcessor:
    """Test DocumentProcessor functionality"""
    
    @pytest.fixture
    def processor(self):
        return DocumentProcessor()
    
    def test_can_process_by_extension(self, processor):
        """Test processor selection by file extension"""
        # Word documents
        assert processor.can_process(ProcessingContext(filename="test.docx")) is True
        assert processor.can_process(ProcessingContext(filename="test.doc")) is True
        
        # Excel documents
        assert processor.can_process(ProcessingContext(filename="test.xlsx")) is True
        assert processor.can_process(ProcessingContext(filename="test.xls")) is True
        
        # CSV files
        assert processor.can_process(ProcessingContext(filename="test.csv")) is True
        
        # Unsupported
        assert processor.can_process(ProcessingContext(filename="test.pdf")) is False
    
    def test_can_process_by_mime_type(self, processor):
        """Test processor selection by MIME type"""
        # Word MIME types
        assert processor.can_process(ProcessingContext(
            mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )) is True
        assert processor.can_process(ProcessingContext(mime_type="application/msword")) is True
        
        # Excel MIME types
        assert processor.can_process(ProcessingContext(
            mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )) is True
        assert processor.can_process(ProcessingContext(mime_type="application/vnd.ms-excel")) is True
        
        # CSV MIME type
        assert processor.can_process(ProcessingContext(mime_type="text/csv")) is True
        
        # Unsupported
        assert processor.can_process(ProcessingContext(mime_type="application/pdf")) is False
    
    def test_detect_file_type(self, processor):
        """Test file type detection logic"""
        # Word documents
        assert processor._detect_file_type(ProcessingContext(filename="test.docx")) == "word"
        assert processor._detect_file_type(ProcessingContext(filename="test.doc")) == "word"
        assert processor._detect_file_type(ProcessingContext(file_path=Path("test.DOCX"))) == "word"
        
        # Excel documents
        assert processor._detect_file_type(ProcessingContext(filename="test.xlsx")) == "excel"
        assert processor._detect_file_type(ProcessingContext(filename="test.xls")) == "excel"
        
        # CSV files
        assert processor._detect_file_type(ProcessingContext(filename="test.csv")) == "csv"
        
        # MIME type detection
        assert processor._detect_file_type(ProcessingContext(
            mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )) == "word"
        assert processor._detect_file_type(ProcessingContext(mime_type="text/csv")) == "csv"
        
        # Unknown
        assert processor._detect_file_type(ProcessingContext(filename="test.unknown")) == "unknown"
    
    @pytest.mark.asyncio
    @patch('src.processors.document_processor.partition_csv')
    async def test_process_csv_success(self, mock_partition, processor, processing_context_csv):
        """Test successful CSV processing"""
        mock_elements = [
            MagicMock(spec=['metadata']),
            MagicMock(spec=['metadata']),
            MagicMock(spec=['metadata'])
        ]
        
        # Header row
        mock_elements[0].__str__ = lambda: "name,email,age"
        mock_elements[0].__class__ = MagicMock(__name__="Text")
        mock_elements[0].metadata.to_dict.return_value = {
            "category": "Text",
            "row_number": 1
        }
        
        # Data rows
        mock_elements[1].__str__ = lambda: "John Doe,john@example.com,30"
        mock_elements[1].__class__ = MagicMock(__name__="Text")
        mock_elements[1].metadata.to_dict.return_value = {
            "category": "Text",
            "row_number": 2
        }
        
        mock_elements[2].__str__ = lambda: "Jane Smith,jane@example.com,25"
        mock_elements[2].__class__ = MagicMock(__name__="Text")
        mock_elements[2].metadata.to_dict.return_value = {
            "category": "Text",
            "row_number": 3
        }
        
        mock_partition.return_value = mock_elements
        
        result = await processor.process(processing_context_csv)
        
        assert result.success is True
        assert len(result.elements) == 3
        assert result.metadata["processor"] == "document"
        assert result.metadata["file_type"] == "csv"
        assert result.elements[0]["row_number"] == 1
        assert result.elements[1]["row_number"] == 2
        assert result.elements[2]["row_number"] == 3
        
        mock_partition.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('src.processors.document_processor.partition_docx')
    async def test_process_word_docx(self, mock_partition, processor):
        """Test Word DOCX processing"""
        mock_elements = [MagicMock(spec=['metadata'])]
        mock_elements[0].__str__ = lambda: "Document title"
        mock_elements[0].__class__ = MagicMock(__name__="Title")
        mock_elements[0].metadata.to_dict.return_value = {
            "category": "Title",
            "page_number": 1
        }
        mock_partition.return_value = mock_elements
        
        context = ProcessingContext(
            filename="test.docx",
            file_path=Path("test.docx"),
            mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        
        result = await processor.process(context)
        
        assert result.success is True
        assert result.metadata["file_type"] == "word"
        assert result.elements[0]["page_number"] == 1
        mock_partition.assert_called_once_with(filename="test.docx")
    
    @pytest.mark.asyncio
    @patch('src.processors.document_processor.partition_doc')
    async def test_process_word_doc(self, mock_partition, processor):
        """Test Word DOC processing"""
        mock_elements = [MagicMock(spec=['metadata'])]
        mock_elements[0].__str__ = lambda: "Legacy document"
        mock_elements[0].__class__ = MagicMock(__name__="Text")
        mock_elements[0].metadata.to_dict.return_value = {"category": "Text"}
        mock_partition.return_value = mock_elements
        
        context = ProcessingContext(
            filename="test.doc",
            file_path=Path("test.doc")
        )
        
        result = await processor.process(context)
        
        assert result.success is True
        assert result.metadata["file_type"] == "word"
        mock_partition.assert_called_once_with(filename="test.doc")
    
    @pytest.mark.asyncio
    @patch('src.processors.document_processor.partition_xlsx')
    async def test_process_excel(self, mock_partition, processor):
        """Test Excel processing"""
        mock_elements = [
            MagicMock(spec=['metadata']),
            MagicMock(spec=['metadata'])
        ]
        
        # Sheet 1 data
        mock_elements[0].__str__ = lambda: "Product A"
        mock_elements[0].__class__ = MagicMock(__name__="Text")
        mock_elements[0].metadata.to_dict.return_value = {
            "category": "Text",
            "sheet_name": "Products",
            "row": 2,
            "column": 1
        }
        
        # Sheet 1 data
        mock_elements[1].__str__ = lambda: "$100"
        mock_elements[1].__class__ = MagicMock(__name__="Text")
        mock_elements[1].metadata.to_dict.return_value = {
            "category": "Text",
            "sheet_name": "Products",
            "row": 2,
            "column": 2
        }
        
        mock_partition.return_value = mock_elements
        
        context = ProcessingContext(
            filename="test.xlsx",
            file_path=Path("test.xlsx")
        )
        
        result = await processor.process(context)
        
        assert result.success is True
        assert result.metadata["file_type"] == "excel"
        assert result.elements[0]["sheet_name"] == "Products"
        assert result.elements[0]["row"] == 2
        assert result.elements[0]["column"] == 1
        mock_partition.assert_called_once_with(filename="test.xlsx")
    
    @pytest.mark.asyncio
    @patch('tempfile.NamedTemporaryFile')
    @patch('os.unlink')
    @patch('src.processors.document_processor.partition_csv')
    async def test_process_with_content_bytes(self, mock_partition, mock_unlink, mock_tempfile, processor, sample_csv_content):
        """Test processing from content bytes using temp file"""
        mock_temp = MagicMock()
        mock_temp.name = "/tmp/test.csv"
        mock_tempfile.return_value.__enter__.return_value = mock_temp
        
        mock_elements = [MagicMock(spec=['metadata'])]
        mock_elements[0].__str__ = lambda: "CSV data from bytes"
        mock_elements[0].__class__ = MagicMock(__name__="Text")
        mock_elements[0].metadata.to_dict.return_value = {"category": "Text"}
        mock_partition.return_value = mock_elements
        
        context = ProcessingContext(
            file_content=sample_csv_content,
            filename="test.csv",
            mime_type="text/csv"
        )
        
        result = await processor.process(context)
        
        assert result.success is True
        mock_temp.write.assert_called_once_with(sample_csv_content)
        mock_partition.assert_called_once_with(filename="/tmp/test.csv")
        mock_unlink.assert_called_once_with("/tmp/test.csv")
    
    @pytest.mark.asyncio
    async def test_process_error_no_content(self, processor):
        """Test error handling when no content provided"""
        context = ProcessingContext(filename="test.docx")  # No file_path or file_content
        
        result = await processor.process(context)
        
        assert result.success is False
        assert "Document processing failed" in result.error
        assert "No valid Word document content provided" in result.error
    
    @pytest.mark.asyncio
    async def test_process_error_unsupported_type(self, processor):
        """Test error handling for unsupported file type"""
        context = ProcessingContext(filename="test.unknown")
        
        result = await processor.process(context)
        
        assert result.success is False
        assert "Unsupported file type: unknown" in result.error
    
    @pytest.mark.asyncio
    @patch('src.processors.document_processor.partition_xlsx')
    async def test_extract_tables_from_excel(self, mock_partition, processor):
        """Test Excel table extraction"""
        mock_elements = [
            MagicMock(spec=['metadata']),
            MagicMock(spec=['metadata']),
            MagicMock(spec=['metadata']),
            MagicMock(spec=['metadata'])
        ]
        
        # Sheet1 data
        mock_elements[0].__str__ = lambda: "Header 1"
        mock_elements[0].metadata.to_dict.return_value = {"sheet_name": "Sheet1"}
        
        mock_elements[1].__str__ = lambda: "Data 1"
        mock_elements[1].metadata.to_dict.return_value = {"sheet_name": "Sheet1"}
        
        # Sheet2 data
        mock_elements[2].__str__ = lambda: "Header 2"
        mock_elements[2].metadata.to_dict.return_value = {"sheet_name": "Sheet2"}
        
        mock_elements[3].__str__ = lambda: "Data 2"
        mock_elements[3].metadata.to_dict.return_value = {"sheet_name": "Sheet2"}
        
        mock_partition.return_value = mock_elements
        
        context = ProcessingContext(
            filename="test.xlsx",
            file_path=Path("test.xlsx")
        )
        
        tables = await processor.extract_tables_from_excel(context)
        
        assert len(tables) == 2
        assert tables[0]["sheet_name"] == "Sheet1"
        assert "Header 1" in tables[0]["rows"]
        assert "Data 1" in tables[0]["rows"]
        assert tables[1]["sheet_name"] == "Sheet2"
        assert "Header 2" in tables[1]["rows"]
        assert "Data 2" in tables[1]["rows"]
    
    @pytest.mark.asyncio
    async def test_extract_tables_from_excel_not_excel(self, processor):
        """Test Excel table extraction on non-Excel file"""
        context = ProcessingContext(filename="test.pdf")
        
        tables = await processor.extract_tables_from_excel(context)
        
        assert tables == []
    
    def test_process_elements_word(self, processor):
        """Test processing elements for Word documents"""
        mock_elements = [
            MagicMock(spec=['metadata']),
            MagicMock(spec=['metadata'])
        ]
        
        # Title element
        mock_elements[0].__str__ = lambda: "Document Title"
        mock_elements[0].__class__ = MagicMock(__name__="Title")
        mock_elements[0].metadata.to_dict.return_value = {
            "category": "Title",
            "page_number": 1,
            "header_footer": False
        }
        
        # Text element
        mock_elements[1].__str__ = lambda: "Document body text"
        mock_elements[1].__class__ = MagicMock(__name__="Text")
        mock_elements[1].metadata.to_dict.return_value = {
            "category": "Text",
            "page_number": 1
        }
        
        result = processor._process_elements(mock_elements, "word")
        
        assert len(result) == 2
        assert result[0]["file_type"] == "word"
        assert result[0]["page_number"] == 1
        assert result[0]["header_footer"] is False
        assert result[1]["file_type"] == "word"
        assert result[1]["page_number"] == 1
    
    def test_process_elements_excel(self, processor):
        """Test processing elements for Excel documents"""
        mock_elements = [MagicMock(spec=['metadata'])]
        
        mock_elements[0].__str__ = lambda: "Excel cell data"
        mock_elements[0].__class__ = MagicMock(__name__="Text")
        mock_elements[0].metadata.to_dict.return_value = {
            "category": "Text",
            "sheet_name": "Sales",
            "row": 3,
            "column": 2
        }
        
        result = processor._process_elements(mock_elements, "excel")
        
        assert len(result) == 1
        assert result[0]["file_type"] == "excel"
        assert result[0]["sheet_name"] == "Sales"
        assert result[0]["row"] == 3
        assert result[0]["column"] == 2
    
    def test_process_elements_csv(self, processor):
        """Test processing elements for CSV files"""
        mock_elements = [MagicMock(spec=['metadata'])]
        
        mock_elements[0].__str__ = lambda: "CSV row data"
        mock_elements[0].__class__ = MagicMock(__name__="Text")
        mock_elements[0].metadata.to_dict.return_value = {
            "category": "Text",
            "row_number": 5
        }
        
        result = processor._process_elements(mock_elements, "csv")
        
        assert len(result) == 1
        assert result[0]["file_type"] == "csv"
        assert result[0]["row_number"] == 5
    
    def test_process_elements_filter_empty(self, processor):
        """Test that empty elements are filtered out"""
        mock_elements = [
            MagicMock(spec=['metadata']),
            MagicMock(spec=['metadata'])
        ]
        
        # Valid element
        mock_elements[0].__str__ = lambda: "Valid content"
        mock_elements[0].__class__ = MagicMock(__name__="Text")
        mock_elements[0].metadata.to_dict.return_value = {"category": "Text"}
        
        # Empty element
        mock_elements[1].__str__ = lambda: "   "  # Only whitespace
        mock_elements[1].__class__ = MagicMock(__name__="Text")
        mock_elements[1].metadata.to_dict.return_value = {"category": "Text"}
        
        result = processor._process_elements(mock_elements, "word")
        
        assert len(result) == 1  # Empty element filtered out
        assert result[0]["text"] == "Valid content"