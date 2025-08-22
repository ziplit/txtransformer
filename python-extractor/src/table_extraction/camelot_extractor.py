"""
Camelot-based table extraction for high-accuracy PDF table parsing
"""

import logging
from typing import Dict, List, Any, Optional, Union
from pathlib import Path

import camelot
import pandas as pd


class CamelotExtractor:
    """Camelot-based table extractor for PDFs"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Default Camelot settings optimized for accuracy
        self.default_lattice_kwargs = {
            'line_scale': 15,
            'copy_text': None,
            'shift_text': [''],
            'split_text': False,
            'flag_size': False,
            'strip_text': '\n'
        }
        
        self.default_stream_kwargs = {
            'row_tol': 2,
            'column_tol': 0,
            'edge_tol': 50,
            'split_text': False,
            'flag_size': False,
        }
    
    def extract_tables(
        self, 
        pdf_path: Union[str, Path], 
        pages: Optional[List[int]] = None,
        table_areas: Optional[List[List[float]]] = None,
        flavor: str = "lattice",
        **kwargs
    ) -> Dict[str, Any]:
        """
        Extract tables using Camelot
        
        Args:
            pdf_path: Path to PDF file
            pages: List of page numbers (1-indexed) to process
            table_areas: List of table areas as [x1, y1, x2, y2] coordinates
            flavor: 'lattice' or 'stream' extraction method
            **kwargs: Additional Camelot parameters
            
        Returns:
            Dictionary with extracted tables and metadata
        """
        try:
            pdf_path = str(pdf_path)
            pages_str = self._format_pages(pages)
            
            self.logger.info("Starting Camelot extraction", extra={
                "pdf_path": pdf_path,
                "pages": pages_str,
                "flavor": flavor,
                "table_areas": len(table_areas) if table_areas else 0
            })
            
            # Prepare extraction parameters
            extract_kwargs = self._prepare_extraction_kwargs(flavor, table_areas, kwargs)
            
            # Extract tables
            tables = camelot.read_pdf(
                pdf_path,
                pages=pages_str,
                flavor=flavor,
                **extract_kwargs
            )
            
            if not tables:
                return {
                    "success": True,
                    "tables": [],
                    "metadata": {"message": "No tables found"}
                }
            
            # Process extracted tables
            processed_tables = []
            for i, table in enumerate(tables):
                processed_table = self._process_camelot_table(table, i)
                processed_tables.append(processed_table)
            
            self.logger.info("Camelot extraction completed", extra={
                "tables_found": len(processed_tables),
                "avg_accuracy": sum(t.get("accuracy", 0) for t in processed_tables) / len(processed_tables)
            })
            
            return {
                "success": True,
                "tables": processed_tables,
                "metadata": {
                    "extractor": "camelot",
                    "flavor": flavor,
                    "total_tables": len(processed_tables)
                }
            }
            
        except Exception as e:
            error_msg = f"Camelot extraction failed: {str(e)}"
            self.logger.error(error_msg)
            return {
                "success": False,
                "tables": [],
                "error": error_msg
            }
    
    def _format_pages(self, pages: Optional[List[int]]) -> str:
        """Format page numbers for Camelot (1-indexed, comma-separated)"""
        if not pages:
            return 'all'
        
        # Convert to 1-indexed for Camelot if pages are 0-indexed
        # If page is already 1+ we keep it, if it's 0-based we convert
        pages_1_indexed = [p if p > 0 else p + 1 for p in pages]
        return ','.join(map(str, pages_1_indexed))
    
    def _prepare_extraction_kwargs(
        self, 
        flavor: str, 
        table_areas: Optional[List[List[float]]], 
        user_kwargs: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Prepare extraction parameters for Camelot"""
        
        # Start with defaults based on flavor
        if flavor == "lattice":
            extract_kwargs = self.default_lattice_kwargs.copy()
        else:  # stream
            extract_kwargs = self.default_stream_kwargs.copy()
        
        # Add table areas if provided
        if table_areas:
            # Convert areas to Camelot format: "x1,y1,x2,y2"
            areas_str = []
            for area in table_areas:
                area_str = ','.join(map(str, area))
                areas_str.append(area_str)
            extract_kwargs['table_areas'] = areas_str
        
        # Override with user parameters
        extract_kwargs.update(user_kwargs)
        
        return extract_kwargs
    
    def _process_camelot_table(self, table, table_index: int) -> Dict[str, Any]:
        """Process a single Camelot table object"""
        try:
            # Get table data as DataFrame
            df = table.df
            
            # Convert DataFrame to list of lists
            data = df.values.tolist()
            headers = df.columns.tolist() if not df.columns.equals(pd.RangeIndex(len(df.columns))) else None
            
            # Get table metadata
            parsing_report = table.parsing_report
            
            processed_table = {
                "table_id": table_index,
                "page": table.page,
                "data": data,
                "headers": headers,
                "rows": len(data),
                "columns": len(data[0]) if data else 0,
                "accuracy": float(parsing_report.get('accuracy', 0)),
                "whitespace": float(parsing_report.get('whitespace', 0)),
                "order": int(parsing_report.get('order', table_index)),
                "extractor": "camelot",
                "bbox": self._extract_bbox(table),
                "metadata": {
                    "parsing_report": parsing_report,
                    "shape": table.shape
                }
            }
            
            # Clean empty rows/columns if needed
            processed_table = self._clean_table_data(processed_table)
            
            return processed_table
            
        except Exception as e:
            self.logger.warning(f"Failed to process Camelot table {table_index}: {str(e)}")
            return {
                "table_id": table_index,
                "page": getattr(table, 'page', 0),
                "data": [],
                "headers": None,
                "rows": 0,
                "columns": 0,
                "accuracy": 0,
                "extractor": "camelot",
                "error": str(e)
            }
    
    def _extract_bbox(self, table) -> Optional[Dict[str, float]]:
        """Extract bounding box from Camelot table"""
        try:
            # Camelot tables have _bbox attribute
            if hasattr(table, '_bbox'):
                bbox = table._bbox
                return {
                    "x1": float(bbox[0]),
                    "y1": float(bbox[1]),
                    "x2": float(bbox[2]),
                    "y2": float(bbox[3])
                }
        except Exception:
            pass
        return None
    
    def _clean_table_data(self, table_data: Dict[str, Any]) -> Dict[str, Any]:
        """Clean table data by removing empty rows/columns"""
        data = table_data["data"]
        
        if not data:
            return table_data
        
        # Remove completely empty rows
        cleaned_data = []
        for row in data:
            if any(str(cell).strip() for cell in row):
                cleaned_data.append(row)
        
        # Update table data
        table_data["data"] = cleaned_data
        table_data["rows"] = len(cleaned_data)
        
        # Note: Column cleaning is more complex and might break table structure
        # So we skip it for now
        
        return table_data
    
    def detect_table_areas(self, pdf_path: Union[str, Path], page: int = 0) -> List[List[float]]:
        """
        Detect potential table areas using Camelot's lattice method
        
        Args:
            pdf_path: Path to PDF file
            page: Page number (0-indexed, will be converted to 1-indexed for Camelot)
            
        Returns:
            List of table areas as [x1, y1, x2, y2] coordinates
        """
        try:
            # Convert to 1-indexed page for Camelot
            camelot_page = page + 1 if page >= 0 else 1
            
            # Use lattice method to detect table structures
            tables = camelot.read_pdf(
                str(pdf_path),
                pages=str(camelot_page),
                flavor='lattice',
                **self.default_lattice_kwargs
            )
            
            areas = []
            for table in tables:
                bbox = self._extract_bbox(table)
                if bbox:
                    areas.append([bbox["x1"], bbox["y1"], bbox["x2"], bbox["y2"]])
            
            self.logger.debug(f"Detected {len(areas)} table areas on page {page}")
            return areas
            
        except Exception as e:
            self.logger.warning(f"Camelot table area detection failed: {str(e)}")
            return []
    
    def get_extraction_stats(self, tables: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Get statistics about extracted tables"""
        if not tables:
            return {"total_tables": 0}
        
        accuracies = [t.get("accuracy", 0) for t in tables]
        
        return {
            "total_tables": len(tables),
            "avg_accuracy": sum(accuracies) / len(accuracies),
            "max_accuracy": max(accuracies),
            "min_accuracy": min(accuracies),
            "high_accuracy_tables": sum(1 for acc in accuracies if acc > 80),
            "pages_with_tables": list(set(t.get("page", 0) for t in tables))
        }