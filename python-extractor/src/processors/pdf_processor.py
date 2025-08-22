"""
PDF processing using Unstructured library with table extraction
"""

import asyncio
import time
from typing import Dict, List, Any, Optional
from pathlib import Path

from unstructured.partition.pdf import partition_pdf
from unstructured.chunking.title import chunk_by_title

from .base_processor import BaseProcessor, ProcessingResult, ProcessingContext
from ..config import settings


class PDFProcessor(BaseProcessor):
    """Processor for PDF files with table extraction capabilities"""
    
    SUPPORTED_EXTENSIONS = {'.pdf'}
    SUPPORTED_MIME_TYPES = {'application/pdf'}
    
    def can_process(self, context: ProcessingContext) -> bool:
        """Check if this processor can handle PDF content"""
        
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
        """Process PDF content with table extraction"""
        start_time = time.time()
        
        try:
            self.logger.info("Starting PDF processing", extra={
                "input_filename": context.filename,
                "file_path": str(context.file_path) if context.file_path else None
            })
            
            # Process PDF in thread pool to avoid blocking
            elements = await asyncio.get_event_loop().run_in_executor(
                None, 
                self._partition_pdf, 
                context
            )
            
            # Convert elements to structured format
            structured_elements = self._process_elements(elements)
            
            # Extract tables specifically
            tables = self._extract_tables(elements)
            
            processing_time = (time.time() - start_time) * 1000
            
            self.logger.info("PDF processing completed", extra={
                "elements_count": len(structured_elements),
                "tables_count": len(tables),
                "processing_time_ms": processing_time
            })
            
            return self._create_success_result(
                elements=structured_elements,
                metadata={
                    "processor": "pdf",
                    "elements_count": len(structured_elements),
                    "tables_count": len(tables),
                    "tables": tables,
                    "source_type": "pdf"
                },
                processing_time_ms=processing_time
            )
            
        except Exception as e:
            error_msg = f"PDF processing failed: {str(e)}"
            self.logger.error(error_msg, extra={
                "input_filename": context.filename,
                "error_type": type(e).__name__
            })
            return self._create_error_result(error_msg)
    
    def _partition_pdf(self, context: ProcessingContext) -> List[Any]:
        """Use Unstructured to partition PDF content"""
        
        # Configure partition options for maximum extraction
        partition_options = {
            "strategy": "hi_res",  # High resolution for better table detection
            "infer_table_structure": True,  # Enable table structure inference
            "extract_images_in_pdf": False,  # We'll handle images separately if needed
            "include_page_breaks": True,
        }
        
        # Add OCR options if enabled
        if settings.ocr_enabled:
            partition_options.update({
                "languages": [settings.ocr_languages],
                "ocr_languages": settings.ocr_languages,
            })
        
        # Add user options
        if context.options:
            partition_options.update(context.options)
        
        # Partition from file or content
        if context.file_path and context.file_path.exists():
            elements = partition_pdf(
                filename=str(context.file_path),
                **partition_options
            )
        elif context.file_content:
            # Write content to temp file for processing
            import tempfile
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_file:
                temp_file.write(context.file_content)
                temp_path = temp_file.name
            
            try:
                elements = partition_pdf(
                    filename=temp_path,
                    **partition_options
                )
            finally:
                # Clean up temp file
                import os
                os.unlink(temp_path)
        else:
            raise ValueError("No valid PDF content provided")
        
        return elements
    
    def _process_elements(self, elements: List[Any]) -> List[Dict[str, Any]]:
        """Process and structure elements from Unstructured"""
        structured_elements = []
        
        for element in elements:
            element_data = {
                "type": str(type(element).__name__),
                "text": self._sanitize_text(str(element)),
                "metadata": self._extract_metadata(element)
            }
            
            # Extract additional PDF-specific information
            if hasattr(element, 'metadata') and element.metadata:
                metadata = element.metadata.to_dict()
                
                # Extract page information
                if 'page_number' in metadata:
                    element_data["page_number"] = metadata['page_number']
                
                # Extract coordinates if available
                for coord_field in ['coordinates', 'coordinate_system']:
                    if coord_field in metadata:
                        element_data[coord_field] = metadata[coord_field]
                
                # Extract element category
                if 'category' in metadata:
                    element_data["category"] = metadata['category']
                
                # Extract parent information for hierarchical structure
                if 'parent_id' in metadata:
                    element_data["parent_id"] = metadata['parent_id']
            
            # Only include elements with meaningful content
            if element_data["text"].strip():
                structured_elements.append(element_data)
        
        return structured_elements
    
    def _extract_tables(self, elements: List[Any]) -> List[Dict[str, Any]]:
        """Extract table information from elements"""
        tables = []
        
        for element in elements:
            element_type = str(type(element).__name__)
            
            # Check if this is a table element
            if element_type == "Table":
                table_data = {
                    "content": str(element),
                    "type": "table",
                    "metadata": self._extract_metadata(element)
                }
                
                # Try to extract structured table data
                if hasattr(element, 'metadata') and element.metadata:
                    metadata = element.metadata.to_dict()
                    
                    if 'text_as_html' in metadata:
                        table_data["html"] = metadata['text_as_html']
                    
                    if 'page_number' in metadata:
                        table_data["page_number"] = metadata['page_number']
                
                tables.append(table_data)
        
        return tables
    
    async def extract_text_only(self, context: ProcessingContext) -> ProcessingResult:
        """Extract only text content, faster processing"""
        start_time = time.time()
        
        try:
            # Use fast strategy for text-only extraction
            context_copy = ProcessingContext(
                file_path=context.file_path,
                file_content=context.file_content,
                filename=context.filename,
                mime_type=context.mime_type,
                options={
                    "strategy": "fast",
                    "infer_table_structure": False,
                    **(context.options or {})
                }
            )
            
            elements = await asyncio.get_event_loop().run_in_executor(
                None, 
                self._partition_pdf, 
                context_copy
            )
            
            # Extract only text elements
            text_elements = []
            full_text = []
            
            for element in elements:
                text = self._sanitize_text(str(element))
                if text:
                    text_elements.append({
                        "type": str(type(element).__name__),
                        "text": text,
                        "metadata": self._extract_metadata(element)
                    })
                    full_text.append(text)
            
            processing_time = (time.time() - start_time) * 1000
            
            return self._create_success_result(
                elements=text_elements,
                metadata={
                    "processor": "pdf_text_only",
                    "elements_count": len(text_elements),
                    "full_text": "\n".join(full_text),
                    "source_type": "pdf"
                },
                processing_time_ms=processing_time
            )
            
        except Exception as e:
            error_msg = f"PDF text extraction failed: {str(e)}"
            self.logger.error(error_msg)
            return self._create_error_result(error_msg)
    
    async def extract_tables_only(self, context: ProcessingContext) -> List[Dict[str, Any]]:
        """Extract only table data for focused processing"""
        try:
            # Use table-optimized strategy
            context_copy = ProcessingContext(
                file_path=context.file_path,
                file_content=context.file_content,
                filename=context.filename,
                mime_type=context.mime_type,
                options={
                    "strategy": "hi_res",
                    "infer_table_structure": True,
                    **(context.options or {})
                }
            )
            
            elements = await asyncio.get_event_loop().run_in_executor(
                None, 
                self._partition_pdf, 
                context_copy
            )
            
            return self._extract_tables(elements)
            
        except Exception as e:
            self.logger.error(f"PDF table extraction failed: {str(e)}")
            return []