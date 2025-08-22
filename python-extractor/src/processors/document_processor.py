"""
Document processor for DOCX, DOC, Excel, and CSV files
"""

import asyncio
import time
from typing import Dict, List, Any, Optional
from pathlib import Path

from unstructured.partition.docx import partition_docx
from unstructured.partition.doc import partition_doc
from unstructured.partition.xlsx import partition_xlsx
from unstructured.partition.csv import partition_csv

from .base_processor import BaseProcessor, ProcessingResult, ProcessingContext
from ..config import settings


class DocumentProcessor(BaseProcessor):
    """Processor for Office documents and spreadsheets"""
    
    SUPPORTED_EXTENSIONS = {'.docx', '.doc', '.xlsx', '.xls', '.csv'}
    SUPPORTED_MIME_TYPES = {
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'application/msword',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'application/vnd.ms-excel',
        'text/csv'
    }
    
    def can_process(self, context: ProcessingContext) -> bool:
        """Check if this processor can handle document content"""
        
        # Check by file extension
        if context.filename:
            path = Path(context.filename)
            if path.suffix.lower() in self.SUPPORTED_EXTENSIONS:
                return True
        
        # Check by file path
        if context.file_path:
            if context.file_path.suffix.lower() in self.SUPPORTED_EXTENSIONS:
                return True
        
        # Check by MIME type
        if context.mime_type:
            if context.mime_type.lower() in self.SUPPORTED_MIME_TYPES:
                return True
        
        return False
    
    async def process(self, context: ProcessingContext) -> ProcessingResult:
        """Process document content based on file type"""
        start_time = time.time()
        
        try:
            file_type = self._detect_file_type(context)
            
            self.logger.info("Starting document processing", extra={
                "input_filename": context.filename,
                "file_type": file_type,
                "file_path": str(context.file_path) if context.file_path else None
            })
            
            # Process document in thread pool to avoid blocking
            elements = await asyncio.get_event_loop().run_in_executor(
                None, 
                self._partition_document, 
                context,
                file_type
            )
            
            # Convert elements to structured format
            structured_elements = self._process_elements(elements, file_type)
            
            processing_time = (time.time() - start_time) * 1000
            
            self.logger.info("Document processing completed", extra={
                "file_type": file_type,
                "elements_count": len(structured_elements),
                "processing_time_ms": processing_time
            })
            
            return self._create_success_result(
                elements=structured_elements,
                metadata={
                    "processor": "document",
                    "file_type": file_type,
                    "elements_count": len(structured_elements),
                    "source_type": file_type
                },
                processing_time_ms=processing_time
            )
            
        except Exception as e:
            error_msg = f"Document processing failed: {str(e)}"
            self.logger.error(error_msg, extra={
                "input_filename": context.filename,
                "error_type": type(e).__name__
            })
            return self._create_error_result(error_msg)
    
    def _detect_file_type(self, context: ProcessingContext) -> str:
        """Detect the file type for appropriate processing"""
        
        # Check file extension first
        if context.filename:
            ext = Path(context.filename).suffix.lower()
            if ext in {'.docx', '.doc'}:
                return 'word'
            elif ext in {'.xlsx', '.xls'}:
                return 'excel'
            elif ext == '.csv':
                return 'csv'
        
        if context.file_path:
            ext = context.file_path.suffix.lower()
            if ext in {'.docx', '.doc'}:
                return 'word'
            elif ext in {'.xlsx', '.xls'}:
                return 'excel'
            elif ext == '.csv':
                return 'csv'
        
        # Check MIME type
        if context.mime_type:
            mime = context.mime_type.lower()
            if 'word' in mime or 'document' in mime:
                return 'word'
            elif 'excel' in mime or 'spreadsheet' in mime:
                return 'excel'
            elif 'csv' in mime:
                return 'csv'
        
        return 'unknown'
    
    def _partition_document(self, context: ProcessingContext, file_type: str) -> List[Any]:
        """Use appropriate Unstructured partitioner based on file type"""
        
        # Base partition options
        partition_options = {}
        
        # Add user options
        if context.options:
            partition_options.update(context.options)
        
        # Choose appropriate partitioner
        if file_type == 'word':
            return self._partition_word_document(context, partition_options)
        elif file_type == 'excel':
            return self._partition_excel_document(context, partition_options)
        elif file_type == 'csv':
            return self._partition_csv_document(context, partition_options)
        else:
            raise ValueError(f"Unsupported file type: {file_type}")
    
    def _partition_word_document(self, context: ProcessingContext, options: Dict[str, Any]) -> List[Any]:
        """Partition Word documents (DOCX/DOC)"""
        
        if context.file_path and context.file_path.exists():
            if context.file_path.suffix.lower() == '.docx':
                return partition_docx(filename=str(context.file_path), **options)
            else:
                return partition_doc(filename=str(context.file_path), **options)
        elif context.file_content:
            # Write content to temp file for processing
            import tempfile
            suffix = '.docx' if context.filename and '.docx' in context.filename else '.doc'
            
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temp_file:
                temp_file.write(context.file_content)
                temp_path = temp_file.name
            
            try:
                if suffix == '.docx':
                    return partition_docx(filename=temp_path, **options)
                else:
                    return partition_doc(filename=temp_path, **options)
            finally:
                import os
                os.unlink(temp_path)
        else:
            raise ValueError("No valid Word document content provided")
    
    def _partition_excel_document(self, context: ProcessingContext, options: Dict[str, Any]) -> List[Any]:
        """Partition Excel documents (XLSX/XLS)"""
        
        if context.file_path and context.file_path.exists():
            return partition_xlsx(filename=str(context.file_path), **options)
        elif context.file_content:
            # Write content to temp file for processing
            import tempfile
            with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as temp_file:
                temp_file.write(context.file_content)
                temp_path = temp_file.name
            
            try:
                return partition_xlsx(filename=temp_path, **options)
            finally:
                import os
                os.unlink(temp_path)
        else:
            raise ValueError("No valid Excel document content provided")
    
    def _partition_csv_document(self, context: ProcessingContext, options: Dict[str, Any]) -> List[Any]:
        """Partition CSV files"""
        
        if context.file_path and context.file_path.exists():
            return partition_csv(filename=str(context.file_path), **options)
        elif context.file_content:
            # Write content to temp file for processing
            import tempfile
            with tempfile.NamedTemporaryFile(suffix='.csv', delete=False, mode='wb') as temp_file:
                temp_file.write(context.file_content)
                temp_path = temp_file.name
            
            try:
                return partition_csv(filename=temp_path, **options)
            finally:
                import os
                os.unlink(temp_path)
        else:
            raise ValueError("No valid CSV content provided")
    
    def _process_elements(self, elements: List[Any], file_type: str) -> List[Dict[str, Any]]:
        """Process and structure elements from Unstructured"""
        structured_elements = []
        
        for element in elements:
            element_data = {
                "type": str(type(element).__name__),
                "text": self._sanitize_text(str(element)),
                "metadata": self._extract_metadata(element),
                "file_type": file_type
            }
            
            # Extract additional metadata based on file type
            if hasattr(element, 'metadata') and element.metadata:
                metadata = element.metadata.to_dict()
                
                # Common metadata
                if 'category' in metadata:
                    element_data["category"] = metadata['category']
                
                # Excel-specific metadata
                if file_type == 'excel':
                    for field in ['sheet_name', 'row', 'column']:
                        if field in metadata:
                            element_data[field] = metadata[field]
                
                # Word document-specific metadata
                elif file_type == 'word':
                    for field in ['page_number', 'header_footer']:
                        if field in metadata:
                            element_data[field] = metadata[field]
                
                # CSV-specific metadata
                elif file_type == 'csv':
                    for field in ['row_number']:
                        if field in metadata:
                            element_data[field] = metadata[field]
            
            # Only include elements with meaningful content
            if element_data["text"].strip():
                structured_elements.append(element_data)
        
        return structured_elements
    
    async def extract_tables_from_excel(self, context: ProcessingContext) -> List[Dict[str, Any]]:
        """Extract tables specifically from Excel files"""
        try:
            if not self._detect_file_type(context) == 'excel':
                return []
            
            elements = await asyncio.get_event_loop().run_in_executor(
                None,
                self._partition_excel_document,
                context,
                {}
            )
            
            tables = []
            current_table = None
            
            for element in elements:
                element_type = str(type(element).__name__)
                text = self._sanitize_text(str(element))
                
                if element_type == "Table" or text:  # Excel partitioning may not use Table type
                    if hasattr(element, 'metadata') and element.metadata:
                        metadata = element.metadata.to_dict()
                        sheet_name = metadata.get('sheet_name', 'Sheet1')
                        
                        if not current_table or current_table['sheet_name'] != sheet_name:
                            if current_table:
                                tables.append(current_table)
                            
                            current_table = {
                                "sheet_name": sheet_name,
                                "rows": [],
                                "metadata": metadata
                            }
                        
                        if text:
                            current_table["rows"].append(text)
            
            if current_table:
                tables.append(current_table)
            
            return tables
            
        except Exception as e:
            self.logger.error(f"Excel table extraction failed: {str(e)}")
            return []