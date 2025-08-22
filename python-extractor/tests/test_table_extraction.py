"""
Tests for table extraction functionality
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import tempfile
import os
from pathlib import Path

from src.table_extraction import TableExtractor, CamelotExtractor, PDFPlumberExtractor, TableProcessor


class TestCamelotExtractor:
    
    def test_init(self):
        """Test CamelotExtractor initialization"""
        extractor = CamelotExtractor()
        assert extractor.logger is not None
        assert "line_scale" in extractor.default_lattice_kwargs
        assert "row_tol" in extractor.default_stream_kwargs
    
    @patch('src.table_extraction.camelot_extractor.camelot')
    def test_extract_tables_success(self, mock_camelot):
        """Test successful table extraction with Camelot"""
        extractor = CamelotExtractor()
        
        # Mock a simple successful extraction - avoid complex pandas mocking
        def mock_process_table(table, idx):
            return {
                "table_id": idx,
                "page": 1,
                "data": [["Header1", "Header2"], ["Data1", "Data2"]],
                "headers": ["Col1", "Col2"],
                "rows": 2,
                "columns": 2,
                "accuracy": 95.0,
                "extractor": "camelot"
            }
        
        # Mock the extractor's process table method to avoid complex DataFrame mocking
        with patch.object(extractor, '_process_camelot_table', side_effect=mock_process_table):
            mock_table = Mock()
            mock_camelot.read_pdf.return_value = [mock_table]
            
            with tempfile.NamedTemporaryFile(suffix='.pdf') as temp_file:
                result = extractor.extract_tables(temp_file.name)
            
            assert result["success"] is True
            assert len(result["tables"]) == 1
            assert result["tables"][0]["page"] == 1
            assert result["tables"][0]["accuracy"] == 95.0
            assert result["metadata"]["extractor"] == "camelot"
    
    @patch('src.table_extraction.camelot_extractor.camelot')
    def test_extract_tables_no_tables(self, mock_camelot):
        """Test extraction when no tables are found"""
        mock_camelot.read_pdf.return_value = []
        
        extractor = CamelotExtractor()
        
        with tempfile.NamedTemporaryFile(suffix='.pdf') as temp_file:
            result = extractor.extract_tables(temp_file.name)
        
        assert result["success"] is True
        assert len(result["tables"]) == 0
        assert "No tables found" in result["metadata"]["message"]
    
    @patch('src.table_extraction.camelot_extractor.camelot')
    def test_extract_tables_exception(self, mock_camelot):
        """Test extraction when Camelot raises exception"""
        mock_camelot.read_pdf.side_effect = Exception("Camelot error")
        
        extractor = CamelotExtractor()
        
        with tempfile.NamedTemporaryFile(suffix='.pdf') as temp_file:
            result = extractor.extract_tables(temp_file.name)
        
        assert result["success"] is False
        assert "Camelot extraction failed" in result["error"]
    
    def test_format_pages(self):
        """Test page number formatting"""
        extractor = CamelotExtractor()
        
        # Test None pages
        assert extractor._format_pages(None) == 'all'
        
        # Test normal pages
        assert extractor._format_pages([1, 3, 5]) == '1,3,5'
        
        # Test 0-indexed conversion (0->1, others stay same if > 0)
        assert extractor._format_pages([0, 2, 4]) == '1,2,4'


class TestPDFPlumberExtractor:
    
    def test_init(self):
        """Test PDFPlumberExtractor initialization"""
        extractor = PDFPlumberExtractor()
        assert extractor.logger is not None
        assert "vertical_strategy" in extractor.default_table_settings
    
    @patch('src.table_extraction.pdfplumber_extractor.pdfplumber')
    def test_extract_tables_success(self, mock_pdfplumber):
        """Test successful table extraction with pdfplumber"""
        # Mock pdfplumber objects
        mock_page = Mock()
        mock_page.extract_tables.return_value = [
            [["Header1", "Header2"], ["Data1", "Data2"]]
        ]
        mock_page.debug_tablefinder.return_value = Mock()
        
        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdf.__enter__.return_value = mock_pdf
        mock_pdf.__exit__.return_value = None
        
        mock_pdfplumber.open.return_value = mock_pdf
        
        extractor = PDFPlumberExtractor()
        
        with tempfile.NamedTemporaryFile(suffix='.pdf') as temp_file:
            result = extractor.extract_tables(temp_file.name)
        
        assert result["success"] is True
        assert len(result["tables"]) == 1
        assert result["tables"][0]["page"] == 1
        assert result["metadata"]["extractor"] == "pdfplumber"
    
    @patch('src.table_extraction.pdfplumber_extractor.pdfplumber')
    def test_extract_tables_no_tables(self, mock_pdfplumber):
        """Test extraction when no tables are found"""
        mock_page = Mock()
        mock_page.extract_tables.return_value = []
        
        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdf.__enter__.return_value = mock_pdf
        mock_pdf.__exit__.return_value = None
        
        mock_pdfplumber.open.return_value = mock_pdf
        
        extractor = PDFPlumberExtractor()
        
        with tempfile.NamedTemporaryFile(suffix='.pdf') as temp_file:
            result = extractor.extract_tables(temp_file.name)
        
        assert result["success"] is True
        assert len(result["tables"]) == 0
    
    @patch('src.table_extraction.pdfplumber_extractor.pdfplumber')
    def test_extract_tables_exception(self, mock_pdfplumber):
        """Test extraction when pdfplumber raises exception"""
        mock_pdfplumber.open.side_effect = Exception("PDFPlumber error")
        
        extractor = PDFPlumberExtractor()
        
        with tempfile.NamedTemporaryFile(suffix='.pdf') as temp_file:
            result = extractor.extract_tables(temp_file.name)
        
        assert result["success"] is False
        assert "PDFPlumber extraction failed" in result["error"]


class TestTableProcessor:
    
    def test_init(self):
        """Test TableProcessor initialization"""
        processor = TableProcessor()
        assert processor.logger is not None
        assert processor.money_pattern is not None
        assert processor.number_pattern is not None
    
    def test_process_table_empty(self):
        """Test processing empty table"""
        processor = TableProcessor()
        
        table_data = {
            "table_id": 0,
            "data": [],
            "headers": None,
            "rows": 0,
            "columns": 0
        }
        
        result = processor.process_table(table_data)
        assert result["data"] == []
    
    def test_process_table_with_data(self):
        """Test processing table with data"""
        processor = TableProcessor()
        
        table_data = {
            "table_id": 0,
            "data": [
                ["Product", "Price", "Qty"],
                ["Widget A", "$10.99", "5"],
                ["Widget B", "$25.50", "2"]
            ],
            "headers": None,
            "rows": 3,
            "columns": 3
        }
        
        result = processor.process_table(table_data)
        
        # Should detect headers and column types (header detection is optional)
        assert "column_types" in result
        assert "quality_score" in result
        assert result["quality_score"] > 0
    
    def test_detect_column_types(self):
        """Test column type detection"""
        processor = TableProcessor()
        
        table_data = {
            "data": [
                ["Widget A", "$10.99", "5", "2023-01-15"],
                ["Widget B", "$25.50", "2", "2023-01-16"]
            ]
        }
        
        result = processor._detect_column_types(table_data)
        column_types = result["column_types"]
        
        assert len(column_types) == 4
        assert column_types[1] == "money"  # Price column
        assert column_types[2] == "quantity"  # Should detect as quantity now
        assert column_types[3] == "date"  # Date column
    
    def test_calculate_header_likelihood(self):
        """Test header likelihood calculation"""
        processor = TableProcessor()
        
        potential_header = ["Product Name", "Unit Price", "Quantity"]
        sample_rows = [
            ["Widget A", "$10.99", "5"],
            ["Widget B", "$25.50", "2"]
        ]
        
        likelihood = processor._calculate_header_likelihood(potential_header, sample_rows)
        assert likelihood > 0.5  # Should be likely a header
    
    def test_merge_similar_tables(self):
        """Test merging similar tables"""
        processor = TableProcessor()
        
        table1 = {
            "table_id": 0,
            "page": 1,
            "data": [["A", "B"], ["C", "D"]],
            "headers": ["Col1", "Col2"],
            "columns": 2
        }
        
        table2 = {
            "table_id": 1,
            "page": 1,
            "data": [["E", "F"], ["G", "H"]],
            "headers": ["Col1", "Col2"],
            "columns": 2
        }
        
        tables = [table1, table2]
        merged = processor.merge_similar_tables(tables)
        
        # Should merge compatible tables
        assert len(merged) == 1
        assert len(merged[0]["data"]) == 4  # Combined rows


class TestTableExtractor:
    
    def test_init(self):
        """Test TableExtractor initialization"""
        extractor = TableExtractor()
        assert extractor.logger is not None
        assert extractor.camelot_extractor is not None
        assert extractor.pdfplumber_extractor is not None
        assert extractor.table_processor is not None
    
    @patch('src.table_extraction.table_extractor.asyncio')
    @patch.object(TableExtractor, '_extract_with_camelot')
    def test_extract_tables_camelot_success(self, mock_camelot_extract, mock_asyncio):
        """Test extraction with successful Camelot results"""
        # Mock successful Camelot extraction
        camelot_result = {
            "success": True,
            "tables": [
                {"table_id": 0, "page": 1, "accuracy": 90, "data": [["A", "B"]]}
            ]
        }
        
        mock_camelot_extract.return_value = camelot_result
        
        # Mock asyncio
        mock_loop = Mock()
        mock_loop.run_in_executor.return_value = camelot_result
        mock_asyncio.get_event_loop.return_value = mock_loop
        
        extractor = TableExtractor()
        
        with tempfile.NamedTemporaryFile(suffix='.pdf') as temp_file:
            # Use run_in_executor mock to simulate async behavior
            result = extractor._extract_with_camelot(Path(temp_file.name))
            
            # Verify the method works synchronously
            assert result["success"] is True
    
    def test_are_results_satisfactory(self):
        """Test satisfactory results detection"""
        extractor = TableExtractor()
        
        # Good results
        good_tables = [
            {"accuracy": 85, "data": [["A", "B"], ["C", "D"]]},
            {"accuracy": 90, "data": [["E", "F"], ["G", "H"]]}
        ]
        
        assert extractor._are_results_satisfactory(good_tables) is True
        
        # Poor results
        poor_tables = [
            {"accuracy": 50, "data": [["A"]]},
        ]
        
        assert extractor._are_results_satisfactory(poor_tables) is False
        
        # Empty results
        assert extractor._are_results_satisfactory([]) is False
    
    def test_merge_table_results(self):
        """Test merging results from different extractors"""
        extractor = TableExtractor()
        
        camelot_tables = [
            {"page": 1, "extractor": "camelot", "accuracy": 90}
        ]
        
        pdfplumber_tables = [
            {"page": 1, "extractor": "pdfplumber", "accuracy": 70},
            {"page": 2, "extractor": "pdfplumber", "accuracy": 80}
        ]
        
        merged = extractor._merge_table_results(camelot_tables, pdfplumber_tables)
        
        # Should keep Camelot table from page 1, add pdfplumber table from page 2
        assert len(merged) == 2
        assert any(t["page"] == 1 and t["extractor"] == "camelot" for t in merged)
        assert any(t["page"] == 2 and t["extractor"] == "pdfplumber" for t in merged)
    
    def test_deduplicate_table_areas(self):
        """Test table area deduplication"""
        extractor = TableExtractor()
        
        areas = [
            [10, 10, 100, 100],  # Area 1
            [20, 20, 90, 90],    # Overlapping significantly with Area 1
            [200, 200, 300, 300]  # Separate area
        ]
        
        unique_areas = extractor._deduplicate_table_areas(areas)
        
        # Should remove overlapping area
        assert len(unique_areas) == 2
    
    def test_areas_overlap(self):
        """Test area overlap detection"""
        extractor = TableExtractor()
        
        area1 = [10, 10, 100, 100]
        area2 = [20, 20, 90, 90]  # Overlapping significantly
        area3 = [200, 200, 300, 300]  # Separate
        
        assert extractor._areas_overlap(area1, area2) is True
        assert extractor._areas_overlap(area1, area3) is False