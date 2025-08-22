"""
Main table extraction orchestrator with fallback strategies
"""

import logging
import asyncio
import time
from typing import Dict, List, Any, Optional, Union
from pathlib import Path
import tempfile
import os

from .camelot_extractor import CamelotExtractor
from .pdfplumber_extractor import PDFPlumberExtractor
from .table_processor import TableProcessor
from ..config import settings


class TableExtractor:
    """
    Main table extraction orchestrator that tries multiple extraction methods
    and selects the best results
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.camelot_extractor = CamelotExtractor()
        self.pdfplumber_extractor = PDFPlumberExtractor()
        self.table_processor = TableProcessor()
        
        self.logger.info("Table Extractor initialized", extra={
            "extractors": ["camelot", "pdfplumber"],
            "fallback_enabled": True
        })
    
    async def extract_tables_from_pdf(
        self, 
        pdf_path: Union[str, Path], 
        pages: Optional[List[int]] = None,
        table_areas: Optional[List[List[float]]] = None,
        extraction_method: str = "auto"
    ) -> Dict[str, Any]:
        """
        Extract tables from PDF using multiple methods with intelligent fallback
        
        Args:
            pdf_path: Path to PDF file
            pages: List of page numbers to process (None for all pages)
            table_areas: List of table areas as [x1, y1, x2, y2] coordinates
            extraction_method: "auto", "camelot", "pdfplumber", or "both"
            
        Returns:
            Dictionary with extracted tables and metadata
        """
        start_time = time.time()
        pdf_path = Path(pdf_path)
        
        if not pdf_path.exists():
            return self._create_error_result(f"PDF file not found: {pdf_path}")
        
        try:
            self.logger.info("Starting table extraction", extra={
                "pdf_path": str(pdf_path),
                "pages": pages,
                "method": extraction_method
            })
            
            results = []
            extraction_methods_used = []
            
            if extraction_method in ["auto", "camelot", "both"]:
                # Try Camelot first (better for complex tables)
                camelot_result = await asyncio.get_event_loop().run_in_executor(
                    None, self._extract_with_camelot, pdf_path, pages, table_areas
                )
                
                if camelot_result["success"] and camelot_result["tables"]:
                    results.extend(camelot_result["tables"])
                    extraction_methods_used.append("camelot")
                    
                    self.logger.info("Camelot extraction successful", extra={
                        "tables_found": len(camelot_result["tables"])
                    })
                    
                    # If we found good tables with Camelot and method is auto, we might be done
                    if extraction_method == "auto" and self._are_results_satisfactory(camelot_result["tables"]):
                        processing_time = (time.time() - start_time) * 1000
                        return self._create_success_result(
                            results, extraction_methods_used, processing_time
                        )
            
            if extraction_method in ["auto", "pdfplumber", "both"]:
                # Try pdfplumber as fallback or primary method
                pdfplumber_result = await asyncio.get_event_loop().run_in_executor(
                    None, self._extract_with_pdfplumber, pdf_path, pages
                )
                
                if pdfplumber_result["success"] and pdfplumber_result["tables"]:
                    # If we already have Camelot results, merge intelligently
                    if results:
                        merged_tables = self._merge_table_results(results, pdfplumber_result["tables"])
                        results = merged_tables
                    else:
                        results.extend(pdfplumber_result["tables"])
                    
                    extraction_methods_used.append("pdfplumber")
                    
                    self.logger.info("PDFPlumber extraction completed", extra={
                        "tables_found": len(pdfplumber_result["tables"])
                    })
            
            processing_time = (time.time() - start_time) * 1000
            
            if results:
                # Post-process all tables
                processed_tables = await self._post_process_tables(results)
                
                return self._create_success_result(
                    processed_tables, extraction_methods_used, processing_time
                )
            else:
                return {
                    "success": False,
                    "tables": [],
                    "error": "No tables found with any extraction method",
                    "metadata": {
                        "extraction_methods_tried": extraction_methods_used,
                        "processing_time_ms": processing_time
                    }
                }
                
        except Exception as e:
            error_msg = f"Table extraction failed: {str(e)}"
            self.logger.error(error_msg, extra={
                "pdf_path": str(pdf_path),
                "error_type": type(e).__name__
            })
            return self._create_error_result(error_msg)
    
    async def extract_tables_from_content(
        self, 
        pdf_content: bytes,
        pages: Optional[List[int]] = None,
        extraction_method: str = "auto"
    ) -> Dict[str, Any]:
        """
        Extract tables from PDF content bytes
        
        Args:
            pdf_content: PDF file content as bytes
            pages: List of page numbers to process
            extraction_method: Extraction method to use
            
        Returns:
            Dictionary with extracted tables and metadata
        """
        # Create temporary file for processing
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_file:
            temp_file.write(pdf_content)
            temp_path = temp_file.name
        
        try:
            result = await self.extract_tables_from_pdf(
                temp_path, pages, extraction_method=extraction_method
            )
            return result
        finally:
            # Clean up temporary file
            os.unlink(temp_path)
    
    def _extract_with_camelot(
        self, 
        pdf_path: Path, 
        pages: Optional[List[int]] = None,
        table_areas: Optional[List[List[float]]] = None
    ) -> Dict[str, Any]:
        """Extract tables using Camelot"""
        try:
            result = self.camelot_extractor.extract_tables(
                pdf_path, pages=pages, table_areas=table_areas
            )
            return result
        except Exception as e:
            self.logger.warning(f"Camelot extraction failed: {str(e)}")
            return {"success": False, "tables": [], "error": str(e)}
    
    def _extract_with_pdfplumber(
        self, 
        pdf_path: Path, 
        pages: Optional[List[int]] = None
    ) -> Dict[str, Any]:
        """Extract tables using pdfplumber"""
        try:
            result = self.pdfplumber_extractor.extract_tables(pdf_path, pages=pages)
            return result
        except Exception as e:
            self.logger.warning(f"PDFPlumber extraction failed: {str(e)}")
            return {"success": False, "tables": [], "error": str(e)}
    
    def _are_results_satisfactory(self, tables: List[Dict[str, Any]]) -> bool:
        """
        Determine if Camelot results are satisfactory enough to skip pdfplumber
        
        Args:
            tables: List of extracted tables
            
        Returns:
            True if results are satisfactory
        """
        if not tables:
            return False
        
        # Check if we have tables with good confidence and reasonable size
        satisfactory_tables = 0
        for table in tables:
            accuracy = table.get("accuracy", 0)
            rows = len(table.get("data", []))
            cols = len(table.get("data", [[]])[0]) if table.get("data") else 0
            
            # Consider satisfactory if accuracy > 80% and table has reasonable dimensions
            if accuracy > 80 and rows >= 2 and cols >= 2:
                satisfactory_tables += 1
        
        # If we have at least one good table, consider it satisfactory
        return satisfactory_tables > 0
    
    def _merge_table_results(
        self, 
        camelot_tables: List[Dict[str, Any]], 
        pdfplumber_tables: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Intelligently merge results from different extraction methods
        
        Args:
            camelot_tables: Tables from Camelot
            pdfplumber_tables: Tables from pdfplumber
            
        Returns:
            Merged list of tables
        """
        merged = []
        
        # For now, use simple strategy: prefer Camelot for its accuracy scores
        # but include pdfplumber tables from pages where Camelot found nothing
        
        camelot_pages = set()
        for table in camelot_tables:
            page = table.get("page", 0)
            camelot_pages.add(page)
            merged.append(table)
        
        # Add pdfplumber tables from pages not covered by Camelot
        for table in pdfplumber_tables:
            page = table.get("page", 0)
            if page not in camelot_pages:
                merged.append(table)
                self.logger.info("Added pdfplumber table from uncovered page", extra={
                    "page": page
                })
        
        return merged
    
    async def _post_process_tables(self, tables: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Post-process extracted tables for better structure"""
        processed_tables = []
        
        for table in tables:
            try:
                processed_table = await asyncio.get_event_loop().run_in_executor(
                    None, self.table_processor.process_table, table
                )
                processed_tables.append(processed_table)
            except Exception as e:
                self.logger.warning(f"Table post-processing failed: {str(e)}")
                # Include original table if processing fails
                processed_tables.append(table)
        
        return processed_tables
    
    def _create_success_result(
        self, 
        tables: List[Dict[str, Any]], 
        methods_used: List[str],
        processing_time: float
    ) -> Dict[str, Any]:
        """Create successful extraction result"""
        return {
            "success": True,
            "tables": tables,
            "metadata": {
                "tables_count": len(tables),
                "extraction_methods_used": methods_used,
                "processing_time_ms": processing_time,
                "pages_with_tables": list(set(t.get("page", 0) for t in tables))
            }
        }
    
    def _create_error_result(self, error_msg: str) -> Dict[str, Any]:
        """Create error result"""
        return {
            "success": False,
            "tables": [],
            "error": error_msg,
            "metadata": {}
        }
    
    async def detect_table_areas(self, pdf_path: Union[str, Path], page: int = 0) -> List[List[float]]:
        """
        Detect potential table areas in a PDF page
        
        Args:
            pdf_path: Path to PDF file
            page: Page number to analyze
            
        Returns:
            List of table areas as [x1, y1, x2, y2] coordinates
        """
        try:
            # Use both methods to detect table areas
            camelot_areas = await asyncio.get_event_loop().run_in_executor(
                None, self.camelot_extractor.detect_table_areas, pdf_path, page
            )
            
            pdfplumber_areas = await asyncio.get_event_loop().run_in_executor(
                None, self.pdfplumber_extractor.detect_table_areas, pdf_path, page
            )
            
            # Merge and deduplicate areas
            all_areas = camelot_areas + pdfplumber_areas
            unique_areas = self._deduplicate_table_areas(all_areas)
            
            self.logger.info("Table area detection completed", extra={
                "page": page,
                "areas_found": len(unique_areas)
            })
            
            return unique_areas
            
        except Exception as e:
            self.logger.error(f"Table area detection failed: {str(e)}")
            return []
    
    def _deduplicate_table_areas(self, areas: List[List[float]]) -> List[List[float]]:
        """Remove duplicate or overlapping table areas"""
        if not areas:
            return []
        
        # Simple deduplication based on area overlap
        unique_areas = []
        
        for area in areas:
            is_duplicate = False
            for existing_area in unique_areas:
                if self._areas_overlap(area, existing_area, threshold=0.7):
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                unique_areas.append(area)
        
        return unique_areas
    
    def _areas_overlap(self, area1: List[float], area2: List[float], threshold: float = 0.5) -> bool:
        """Check if two table areas overlap significantly"""
        x1_1, y1_1, x2_1, y2_1 = area1
        x1_2, y1_2, x2_2, y2_2 = area2
        
        # Calculate overlap
        overlap_x = max(0, min(x2_1, x2_2) - max(x1_1, x1_2))
        overlap_y = max(0, min(y2_1, y2_2) - max(y1_1, y1_2))
        overlap_area = overlap_x * overlap_y
        
        # Calculate areas
        area1_size = (x2_1 - x1_1) * (y2_1 - y1_1)
        area2_size = (x2_2 - x1_2) * (y2_2 - y1_2)
        
        # Calculate overlap ratio
        if area1_size == 0 or area2_size == 0:
            return False
        
        overlap_ratio = overlap_area / min(area1_size, area2_size)
        return overlap_ratio > threshold