"""
Post-processing utilities for extracted tables to improve structure and data quality
"""

import logging
import re
from typing import Dict, List, Any, Optional, Tuple
import pandas as pd
from decimal import Decimal, InvalidOperation


class TableProcessor:
    """Post-processor for cleaning and structuring extracted table data"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Common patterns for data type detection
        self.money_pattern = re.compile(r'^\$\s*[\d,]+\.?\d*\s*$|^\s*[\d,]+\.\d+\s*$')
        self.date_patterns = [
            re.compile(r'\d{1,2}/\d{1,2}/\d{2,4}'),  # MM/DD/YYYY or MM/DD/YY
            re.compile(r'\d{1,2}-\d{1,2}-\d{2,4}'),  # MM-DD-YYYY or MM-DD-YY
            re.compile(r'\d{4}-\d{1,2}-\d{1,2}'),    # YYYY-MM-DD
            re.compile(r'\w+\s+\d{1,2},?\s+\d{4}'),  # Month DD, YYYY
        ]
        self.number_pattern = re.compile(r'^\s*[\d,]+\.?\d*\s*$')
        self.quantity_pattern = re.compile(r'^\s*\d+\s*(pcs?|pieces?|units?|each|qty|x)?\s*$', re.IGNORECASE)
        
    def process_table(self, table_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Post-process a table to improve data quality and structure
        
        Args:
            table_data: Raw table data from extractor
            
        Returns:
            Enhanced table data with better structure
        """
        try:
            if not table_data.get("data") or len(table_data["data"]) == 0:
                return table_data
            
            processed_table = table_data.copy()
            
            # Clean and normalize table data
            processed_table = self._clean_table_data(processed_table)
            
            # Detect and improve headers
            processed_table = self._improve_headers(processed_table)
            
            # Detect column types
            processed_table = self._detect_column_types(processed_table)
            
            # Extract structured data patterns
            processed_table = self._extract_structured_patterns(processed_table)
            
            # Add quality metrics
            processed_table = self._calculate_quality_metrics(processed_table)
            
            self.logger.debug(f"Processed table {table_data.get('table_id', 'unknown')}")
            
            return processed_table
            
        except Exception as e:
            self.logger.warning(f"Table processing failed: {str(e)}")
            return table_data
    
    def _clean_table_data(self, table_data: Dict[str, Any]) -> Dict[str, Any]:
        """Clean and normalize table cell data"""
        data = table_data["data"]
        cleaned_data = []
        
        for row in data:
            cleaned_row = []
            for cell in row:
                # Convert to string and clean whitespace
                cleaned_cell = str(cell).strip() if cell is not None else ""
                
                # Remove excessive whitespace
                cleaned_cell = re.sub(r'\s+', ' ', cleaned_cell)
                
                # Remove common OCR artifacts
                cleaned_cell = re.sub(r'[|]{2,}', '|', cleaned_cell)  # Multiple pipes
                cleaned_cell = re.sub(r'[-]{3,}', '-', cleaned_cell)  # Multiple dashes
                
                cleaned_row.append(cleaned_cell)
            
            # Only include row if it has meaningful content
            if any(cell.strip() for cell in cleaned_row):
                cleaned_data.append(cleaned_row)
        
        table_data["data"] = cleaned_data
        table_data["rows"] = len(cleaned_data)
        
        return table_data
    
    def _improve_headers(self, table_data: Dict[str, Any]) -> Dict[str, Any]:
        """Detect and improve table headers"""
        data = table_data["data"]
        
        if len(data) == 0:
            return table_data
        
        # If no headers detected, try to detect them
        if not table_data.get("headers") and len(data) > 1:
            potential_header = data[0]
            
            # Check if first row looks like a header
            header_score = self._calculate_header_likelihood(potential_header, data[1:3])
            
            if header_score > 0.6:
                table_data["headers"] = potential_header
                table_data["data"] = data[1:]
                table_data["rows"] = len(data) - 1
                self.logger.debug("Detected header row during post-processing")
        
        # Clean headers if they exist
        if table_data.get("headers"):
            cleaned_headers = []
            for header in table_data["headers"]:
                # Clean header text
                cleaned_header = str(header).strip().title()
                # Remove common noise
                cleaned_header = re.sub(r'[^\w\s]', '', cleaned_header)
                cleaned_headers.append(cleaned_header)
            
            table_data["headers"] = cleaned_headers
        
        return table_data
    
    def _calculate_header_likelihood(self, potential_header: List[str], sample_rows: List[List[str]]) -> float:
        """Calculate likelihood that a row is a header based on content patterns"""
        if not sample_rows:
            return 0.0
        
        score = 0.0
        total_cols = len(potential_header)
        
        for col_idx in range(total_cols):
            header_cell = potential_header[col_idx].strip()
            
            if not header_cell:
                continue
            
            # Headers are more likely to:
            # 1. Contain text (not numbers)
            if not self.number_pattern.match(header_cell):
                score += 0.3
            
            # 2. Be shorter than data cells
            sample_cells = [row[col_idx] for row in sample_rows if col_idx < len(row)]
            avg_sample_length = sum(len(str(cell)) for cell in sample_cells) / len(sample_cells) if sample_cells else 0
            
            if len(header_cell) <= avg_sample_length:
                score += 0.2
            
            # 3. Contain descriptive words
            descriptive_words = ['name', 'id', 'date', 'price', 'amount', 'quantity', 'description', 'total', 'sku']
            if any(word in header_cell.lower() for word in descriptive_words):
                score += 0.3
        
        return score / total_cols if total_cols > 0 else 0.0
    
    def _detect_column_types(self, table_data: Dict[str, Any]) -> Dict[str, Any]:
        """Detect data types for each column"""
        data = table_data["data"]
        
        if not data:
            return table_data
        
        num_cols = len(data[0]) if data else 0
        column_types = []
        
        for col_idx in range(num_cols):
            column_cells = [row[col_idx] for row in data if col_idx < len(row) and row[col_idx].strip()]
            
            if not column_cells:
                column_types.append("empty")
                continue
            
            # Analyze cell patterns
            type_scores = {
                "money": 0,
                "date": 0,
                "number": 0,
                "quantity": 0,
                "text": 0
            }
            
            for cell in column_cells[:10]:  # Sample first 10 cells
                cell = cell.strip()
                
                # Check in order of specificity
                if self.money_pattern.match(cell):
                    type_scores["money"] += 1
                elif self.quantity_pattern.match(cell):
                    type_scores["quantity"] += 1
                elif any(pattern.match(cell) for pattern in self.date_patterns):
                    type_scores["date"] += 1
                elif self.number_pattern.match(cell):
                    type_scores["number"] += 1
                else:
                    type_scores["text"] += 1
            
            # Determine most likely type
            detected_type = max(type_scores.items(), key=lambda x: x[1])[0]
            column_types.append(detected_type)
        
        table_data["column_types"] = column_types
        return table_data
    
    def _extract_structured_patterns(self, table_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract structured data patterns like line items, totals, etc."""
        data = table_data["data"]
        
        if not data:
            return table_data
        
        patterns_found = {
            "has_totals": False,
            "has_line_items": False,
            "has_quantities": False,
            "has_prices": False
        }
        
        # Check for totals (usually in last few rows)
        for row in data[-3:]:
            for cell in row:
                cell_lower = cell.lower().strip()
                if any(word in cell_lower for word in ['total', 'subtotal', 'sum', 'grand']):
                    patterns_found["has_totals"] = True
                    break
        
        # Check for line items pattern (multiple rows with similar structure)
        if len(data) >= 3:
            patterns_found["has_line_items"] = True
        
        # Check for quantities and prices based on column types
        column_types = table_data.get("column_types", [])
        patterns_found["has_quantities"] = "quantity" in column_types
        patterns_found["has_prices"] = "money" in column_types
        
        table_data["patterns"] = patterns_found
        return table_data
    
    def _calculate_quality_metrics(self, table_data: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate quality metrics for the processed table"""
        data = table_data["data"]
        
        if not data:
            table_data["quality_score"] = 0
            return table_data
        
        total_cells = sum(len(row) for row in data)
        empty_cells = sum(1 for row in data for cell in row if not cell.strip())
        
        # Base quality metrics
        completeness = (total_cells - empty_cells) / total_cells if total_cells > 0 else 0
        
        # Structure quality
        has_headers = bool(table_data.get("headers"))
        consistent_columns = len(set(len(row) for row in data)) == 1
        
        # Content quality based on detected types
        column_types = table_data.get("column_types", [])
        typed_columns = sum(1 for col_type in column_types if col_type != "text")
        type_diversity = typed_columns / len(column_types) if column_types else 0
        
        # Calculate overall quality score
        quality_components = {
            "completeness": completeness * 0.4,
            "structure": (0.2 if has_headers else 0) + (0.2 if consistent_columns else 0),
            "content": type_diversity * 0.2
        }
        
        quality_score = sum(quality_components.values()) * 100
        
        # Update or preserve accuracy from original extractor
        original_accuracy = table_data.get("accuracy", 0)
        if original_accuracy > 0:
            # Blend with original accuracy (weight original more heavily)
            blended_accuracy = (original_accuracy * 0.7) + (quality_score * 0.3)
            table_data["accuracy"] = min(100, blended_accuracy)
        else:
            table_data["accuracy"] = quality_score
        
        table_data["quality_score"] = quality_score
        table_data["quality_components"] = quality_components
        
        return table_data
    
    def merge_similar_tables(self, tables: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Merge tables that appear to be parts of the same logical table"""
        if len(tables) <= 1:
            return tables
        
        merged_tables = []
        skip_indices = set()
        
        for i, table in enumerate(tables):
            if i in skip_indices:
                continue
            
            current_table = table.copy()
            
            # Look for tables on the same page that could be merged
            for j in range(i + 1, len(tables)):
                if j in skip_indices:
                    continue
                
                other_table = tables[j]
                
                # Check if tables can be merged
                if self._can_merge_tables(current_table, other_table):
                    current_table = self._merge_two_tables(current_table, other_table)
                    skip_indices.add(j)
                    self.logger.debug(f"Merged table {i} with table {j}")
            
            merged_tables.append(current_table)
        
        return merged_tables
    
    def _can_merge_tables(self, table1: Dict[str, Any], table2: Dict[str, Any]) -> bool:
        """Check if two tables can be merged"""
        # Must be on same page
        if table1.get("page") != table2.get("page"):
            return False
        
        # Must have same number of columns or compatible structure
        cols1 = table1.get("columns", 0)
        cols2 = table2.get("columns", 0)
        
        if abs(cols1 - cols2) > 1:  # Allow for slight column differences
            return False
        
        # Check if headers are compatible
        headers1 = table1.get("headers", [])
        headers2 = table2.get("headers", [])
        
        if headers1 and headers2:
            # If both have headers, they should match
            if len(headers1) == len(headers2):
                similarity = sum(1 for h1, h2 in zip(headers1, headers2) if h1.lower() == h2.lower())
                if similarity / len(headers1) < 0.7:  # At least 70% header similarity
                    return False
        
        return True
    
    def _merge_two_tables(self, table1: Dict[str, Any], table2: Dict[str, Any]) -> Dict[str, Any]:
        """Merge two compatible tables"""
        merged_table = table1.copy()
        
        # Combine data
        data1 = table1.get("data", [])
        data2 = table2.get("data", [])
        
        # If table2 has headers that match table1, skip them
        headers1 = table1.get("headers", [])
        if headers1 and data2 and len(data2[0]) == len(headers1):
            first_row_similarity = sum(
                1 for h1, cell in zip(headers1, data2[0]) 
                if h1.lower() == cell.lower().strip()
            )
            if first_row_similarity / len(headers1) > 0.7:
                data2 = data2[1:]  # Skip header row
        
        merged_data = data1 + data2
        
        # Update merged table properties
        merged_table["data"] = merged_data
        merged_table["rows"] = len(merged_data)
        merged_table["metadata"] = merged_table.get("metadata", {})
        merged_table["metadata"]["merged_from"] = [
            table1.get("table_id", "unknown"),
            table2.get("table_id", "unknown")
        ]
        
        # Recalculate quality metrics
        merged_table = self._calculate_quality_metrics(merged_table)
        
        return merged_table