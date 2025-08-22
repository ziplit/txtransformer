"""
Email processing using Unstructured library
"""

import asyncio
import time
from typing import Dict, List, Any
from pathlib import Path

from unstructured.partition.email import partition_email
from unstructured.staging.base import elements_to_json

from .base_processor import BaseProcessor, ProcessingResult, ProcessingContext
from ..config import settings


class EmailProcessor(BaseProcessor):
    """Processor for email files (.eml, .msg)"""
    
    SUPPORTED_EXTENSIONS = {'.eml', '.msg'}
    SUPPORTED_MIME_TYPES = {
        'message/rfc822',
        'application/vnd.ms-outlook',
        'message/x-emlx'
    }
    
    def can_process(self, context: ProcessingContext) -> bool:
        """Check if this processor can handle email content"""
        
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
        """Process email content and extract structured elements"""
        start_time = time.time()
        
        try:
            self.logger.info("Starting email processing", extra={
                "input_filename": context.filename,
                "file_path": str(context.file_path) if context.file_path else None,
                "mime_type": context.mime_type
            })
            
            # Process email in thread pool to avoid blocking
            elements = await asyncio.get_event_loop().run_in_executor(
                None, 
                self._partition_email, 
                context
            )
            
            # Convert elements to structured format
            structured_elements = self._process_elements(elements)
            
            processing_time = (time.time() - start_time) * 1000
            
            self.logger.info("Email processing completed", extra={
                "elements_count": len(structured_elements),
                "processing_time_ms": processing_time
            })
            
            return self._create_success_result(
                elements=structured_elements,
                metadata={
                    "processor": "email",
                    "elements_count": len(structured_elements),
                    "source_type": "email"
                },
                processing_time_ms=processing_time
            )
            
        except Exception as e:
            error_msg = f"Email processing failed: {str(e)}"
            self.logger.error(error_msg, extra={
                "input_filename": context.filename,
                "error_type": type(e).__name__
            })
            return self._create_error_result(error_msg)
    
    def _partition_email(self, context: ProcessingContext) -> List[Any]:
        """Use Unstructured to partition email content"""
        
        # Configure partition options
        partition_options = {
            "include_headers": True,
            "process_attachments": False,  # We'll handle attachments separately
        }
        
        # Add user options
        if context.options:
            partition_options.update(context.options)
        
        # Partition from file or content
        if context.file_path and context.file_path.exists():
            elements = partition_email(
                filename=str(context.file_path),
                **partition_options
            )
        elif context.file_content:
            elements = partition_email(
                file=context.file_content,
                **partition_options
            )
        else:
            raise ValueError("No valid email content provided")
        
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
            
            # Extract additional email-specific information
            if hasattr(element, 'metadata') and element.metadata:
                metadata = element.metadata.to_dict()
                
                # Extract email headers
                if 'email_headers' in metadata:
                    element_data["email_headers"] = metadata['email_headers']
                
                # Extract sender/recipient information
                for field in ['sender', 'recipient', 'subject', 'date']:
                    if field in metadata:
                        element_data[field] = metadata[field]
                
                # Extract element category
                if 'category' in metadata:
                    element_data["category"] = metadata['category']
            
            # Only include elements with meaningful content
            if element_data["text"].strip():
                structured_elements.append(element_data)
        
        return structured_elements
    
    async def extract_headers(self, context: ProcessingContext) -> Dict[str, Any]:
        """Extract email headers specifically"""
        try:
            elements = await asyncio.get_event_loop().run_in_executor(
                None, 
                self._partition_email, 
                context
            )
            
            headers = {}
            for element in elements:
                if hasattr(element, 'metadata') and element.metadata:
                    metadata = element.metadata.to_dict()
                    if 'email_headers' in metadata:
                        headers.update(metadata['email_headers'])
            
            return headers
            
        except Exception as e:
            self.logger.error(f"Header extraction failed: {str(e)}")
            return {}
    
    async def extract_attachments_info(self, context: ProcessingContext) -> List[Dict[str, Any]]:
        """Extract information about email attachments"""
        try:
            # Process with attachment metadata
            partition_options = {
                "include_headers": True,
                "process_attachments": True,
                "attachment_partitioner": lambda x: []  # Don't process attachment content
            }
            
            if context.options:
                partition_options.update(context.options)
            
            elements = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: partition_email(
                    filename=str(context.file_path) if context.file_path else None,
                    file=context.file_content,
                    **partition_options
                )
            )
            
            attachments = []
            for element in elements:
                if hasattr(element, 'metadata') and element.metadata:
                    metadata = element.metadata.to_dict()
                    if 'attached_to_filename' in metadata:
                        attachments.append({
                            "filename": metadata.get('attached_to_filename'),
                            "content_type": metadata.get('file_directory', ''),
                            "size": metadata.get('file_size'),
                        })
            
            return attachments
            
        except Exception as e:
            self.logger.error(f"Attachment info extraction failed: {str(e)}")
            return []