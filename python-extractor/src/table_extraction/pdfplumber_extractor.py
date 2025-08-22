"""
pdfplumber-based table extraction for fallback PDF table parsing
"""

import logging
from typing import Dict, List, Any, Optional, Union
from pathlib import Path
import pdfplumber
import pandas as pd


class PDFPlumberExtractor:
    """PDFPlumber-based table extractor for PDFs"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Default settings optimized for accuracy
        self.default_table_settings = {
            'vertical_strategy': 'lines',
            'horizontal_strategy': 'lines',
            'explicit_vertical_lines': [],
            'explicit_horizontal_lines': [],
            'snap_tolerance': 3,
            'join_tolerance': 3,
            'edge_min_length': 3,
            'min_words_vertical': 3,
            'min_words_horizontal': 1,
            'intersection_tolerance': 3,
            'intersection_x_tolerance': None,
            'intersection_y_tolerance': None,
            'keep_blank_chars': False,
            'text_tolerance': 3,
            'text_x_tolerance': None,
            'text_y_tolerance': None
        }
    
    def extract_tables(
        self, 
        pdf_path: Union[str, Path], 
        pages: Optional[List[int]] = None,
        table_settings: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Extract tables using pdfplumber
        
        Args:
            pdf_path: Path to PDF file
            pages: List of page numbers (0-indexed) to process
            table_settings: Custom table extraction settings
            
        Returns:
            Dictionary with extracted tables and metadata
        """
        try:
            pdf_path = Path(pdf_path)
            
            self.logger.info("Starting pdfplumber extraction", extra={
                "pdf_path": str(pdf_path),
                "pages": pages
            })
            
            # Prepare table settings
            settings = self.default_table_settings.copy()
            if table_settings:
                settings.update(table_settings)
            
            extracted_tables = []
            
            with pdfplumber.open(pdf_path) as pdf:
                # Determine pages to process
                if pages is None:
                    pages_to_process = range(len(pdf.pages))
                else:
                    # Convert to 0-indexed if needed
                    pages_to_process = [p if p >= 0 else p for p in pages]
                    pages_to_process = [p for p in pages_to_process if 0 <= p < len(pdf.pages)]
                
                for page_num in pages_to_process:
                    page = pdf.pages[page_num]
                    
                    # Extract tables from this page
                    page_tables = page.extract_tables(table_settings=settings)
                    
                    for table_idx, table_data in enumerate(page_tables):
                        if table_data and len(table_data) > 0:
                            processed_table = self._process_pdfplumber_table(
                                table_data, page_num, table_idx, page
                            )
                            extracted_tables.append(processed_table)
            
            self.logger.info("PDFPlumber extraction completed", extra={
                "tables_found": len(extracted_tables)
            })
            
            return {
                "success": True,
                "tables": extracted_tables,
                "metadata": {
                    "extractor": "pdfplumber",
                    "total_tables": len(extracted_tables),
                    "pages_processed": len(pages_to_process) if pages else "all"
                }
            }
            
        except Exception as e:
            error_msg = f"PDFPlumber extraction failed: {str(e)}"
            self.logger.error(error_msg)
            return {
                "success": False,
                "tables": [],
                "error": error_msg
            }
    
    def _process_pdfplumber_table(
        self, 
        table_data: List[List[str]], 
        page_num: int, 
        table_idx: int,
        page_obj
    ) -> Dict[str, Any]:
        """Process a single pdfplumber table"""
        try:
            # Clean the table data
            cleaned_data = []
            for row in table_data:
                cleaned_row = []
                for cell in row:
                    # Handle None values and clean whitespace
                    cleaned_cell = str(cell).strip() if cell is not None else ""
                    cleaned_row.append(cleaned_cell)
                cleaned_data.append(cleaned_row)
            
            # Remove completely empty rows
            cleaned_data = [row for row in cleaned_data if any(cell.strip() for cell in row)]
            
            if not cleaned_data:
                return {
                    "table_id": table_idx,
                    "page": page_num + 1,  # Convert to 1-indexed for consistency
                    "data": [],
                    "headers": None,
                    "rows": 0,
                    "columns": 0,
                    "extractor": "pdfplumber"
                }
            
            # Detect headers (first row if it looks different)
            headers = None
            if len(cleaned_data) > 1:
                # Simple heuristic: if first row has fewer empty cells, treat as header
                first_row_empty = sum(1 for cell in cleaned_data[0] if not cell.strip())
                other_rows_avg_empty = sum(
                    sum(1 for cell in row if not cell.strip())
                    for row in cleaned_data[1:3]  # Check next 2 rows
                ) / min(2, len(cleaned_data) - 1)
                
                if first_row_empty < other_rows_avg_empty:
                    headers = cleaned_data[0]
                    cleaned_data = cleaned_data[1:]
            
            # Calculate basic statistics
            num_rows = len(cleaned_data)
            num_cols = len(cleaned_data[0]) if cleaned_data else 0
            
            # Calculate confidence based on table completeness
            total_cells = num_rows * num_cols
            empty_cells = sum(
                1 for row in cleaned_data 
                for cell in row if not cell.strip()
            ) if total_cells > 0 else 0
            
            completeness = (total_cells - empty_cells) / total_cells if total_cells > 0 else 0
            confidence = min(95, completeness * 100)  # Cap at 95% since we don't have accuracy metrics
            
            # Try to extract bounding box from page
            bbox = self._extract_table_bbox(page_obj, table_idx)
            
            processed_table = {
                "table_id": table_idx,
                "page": page_num + 1,  # Convert to 1-indexed for consistency
                "data": cleaned_data,
                "headers": headers,
                "rows": num_rows,
                "columns": num_cols,
                "accuracy": confidence,  # Use completeness as proxy for accuracy
                "extractor": "pdfplumber",
                "bbox": bbox,
                "metadata": {
                    "completeness": completeness,
                    "empty_cells": empty_cells,
                    "total_cells": total_cells
                }
            }
            
            return processed_table
            
        except Exception as e:
            self.logger.warning(f"Failed to process pdfplumber table {table_idx} on page {page_num}: {str(e)}")
            return {
                "table_id": table_idx,
                "page": page_num + 1,
                "data": [],
                "headers": None,
                "rows": 0,
                "columns": 0,
                "accuracy": 0,
                "extractor": "pdfplumber",
                "error": str(e)
            }
    
    def _extract_table_bbox(self, page_obj, table_idx: int) -> Optional[Dict[str, float]]:
        """Extract bounding box from pdfplumber page objects"""
        try:
            # Get table objects from page
            table_finder = page_obj.debug_tablefinder()
            if table_finder and hasattr(table_finder, 'tables'):
                tables = table_finder.tables
                if table_idx < len(tables):
                    table = tables[table_idx]
                    if hasattr(table, 'bbox'):
                        x1, y1, x2, y2 = table.bbox
                        return {
                            "x1": float(x1),
                            "y1": float(y1),
                            "x2": float(x2),
                            "y2": float(y2)
                        }
        except Exception:
            pass
        
        return None
    
    def detect_table_areas(self, pdf_path: Union[str, Path], page: int = 0) -> List[List[float]]:
        """
        Detect potential table areas using pdfplumber
        
        Args:
            pdf_path: Path to PDF file
            page: Page number (0-indexed)
            
        Returns:
            List of table areas as [x1, y1, x2, y2] coordinates
        """
        try:
            areas = []
            
            with pdfplumber.open(pdf_path) as pdf:
                if 0 <= page < len(pdf.pages):
                    page_obj = pdf.pages[page]
                    
                    # Use table finder to detect potential table areas
                    table_finder = page_obj.debug_tablefinder()
                    if table_finder and hasattr(table_finder, 'tables'):
                        for table in table_finder.tables:
                            if hasattr(table, 'bbox'):
                                x1, y1, x2, y2 = table.bbox
                                areas.append([float(x1), float(y1), float(x2), float(y2)])
            
            self.logger.debug(f"Detected {len(areas)} potential table areas on page {page}")
            return areas
            
        except Exception as e:
            self.logger.warning(f"PDFPlumber table area detection failed: {str(e)}")
            return []
    
    def get_extraction_stats(self, tables: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Get statistics about extracted tables"""
        if not tables:
            return {"total_tables": 0}
        
        completeness_scores = [
            t.get("metadata", {}).get("completeness", 0) for t in tables
        ]
        
        return {
            "total_tables": len(tables),
            "avg_completeness": sum(completeness_scores) / len(completeness_scores),
            "max_completeness": max(completeness_scores),
            "min_completeness": min(completeness_scores),
            "high_completeness_tables": sum(1 for comp in completeness_scores if comp > 0.8),
            "pages_with_tables": list(set(t.get("page", 0) for t in tables))
        }