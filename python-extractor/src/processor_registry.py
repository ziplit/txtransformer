"""
Processor registry for managing document processors
"""

import logging
from typing import List, Dict, Any, Optional
from pathlib import Path

from .processors.base_processor import BaseProcessor, ProcessingContext, ProcessingResult
from .processors.email_processor import EmailProcessor
from .processors.pdf_processor import PDFProcessor
from .processors.document_processor import DocumentProcessor


class ProcessorRegistry:
    """Registry for managing and selecting document processors"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.processors: List[BaseProcessor] = []
        self._register_default_processors()
    
    def _register_default_processors(self):
        """Register default processors"""
        self.processors = [
            EmailProcessor(),
            PDFProcessor(),
            DocumentProcessor(),
        ]
        
        self.logger.info("Registered default processors", extra={
            "processors": [type(p).__name__ for p in self.processors]
        })
    
    def register_processor(self, processor: BaseProcessor):
        """Register a custom processor"""
        self.processors.append(processor)
        self.logger.info(f"Registered custom processor: {type(processor).__name__}")
    
    def get_processor(self, context: ProcessingContext) -> Optional[BaseProcessor]:
        """Get the appropriate processor for the given context"""
        
        for processor in self.processors:
            if processor.can_process(context):
                self.logger.debug(f"Selected processor: {type(processor).__name__}", extra={
                    "input_filename": context.filename,
                    "mime_type": context.mime_type
                })
                return processor
        
        self.logger.warning("No suitable processor found", extra={
            "input_filename": context.filename,
            "mime_type": context.mime_type
        })
        return None
    
    async def process_document(
        self, 
        context: ProcessingContext
    ) -> ProcessingResult:
        """Process a document using the appropriate processor"""
        
        processor = self.get_processor(context)
        
        if not processor:
            return ProcessingResult(
                success=False,
                elements=[],
                metadata={},
                error=f"No processor available for file type: {context.mime_type or 'unknown'}"
            )
        
        try:
            result = await processor.process(context)
            
            # Add registry metadata
            result.metadata["selected_processor"] = type(processor).__name__
            
            return result
            
        except Exception as e:
            error_msg = f"Processing failed with {type(processor).__name__}: {str(e)}"
            self.logger.error(error_msg, extra={
                "processor": type(processor).__name__,
                "input_filename": context.filename,
                "error_type": type(e).__name__
            })
            
            return ProcessingResult(
                success=False,
                elements=[],
                metadata={"selected_processor": type(processor).__name__},
                error=error_msg
            )
    
    def get_supported_types(self) -> Dict[str, List[str]]:
        """Get all supported file types and MIME types"""
        
        supported = {
            "extensions": [],
            "mime_types": []
        }
        
        for processor in self.processors:
            if hasattr(processor, 'SUPPORTED_EXTENSIONS'):
                supported["extensions"].extend(processor.SUPPORTED_EXTENSIONS)
            
            if hasattr(processor, 'SUPPORTED_MIME_TYPES'):
                supported["mime_types"].extend(processor.SUPPORTED_MIME_TYPES)
        
        # Remove duplicates and sort
        supported["extensions"] = sorted(list(set(supported["extensions"])))
        supported["mime_types"] = sorted(list(set(supported["mime_types"])))
        
        return supported
    
    def get_processor_info(self) -> List[Dict[str, Any]]:
        """Get information about all registered processors"""
        
        info = []
        
        for processor in self.processors:
            processor_info = {
                "name": type(processor).__name__,
                "supported_extensions": getattr(processor, 'SUPPORTED_EXTENSIONS', set()),
                "supported_mime_types": getattr(processor, 'SUPPORTED_MIME_TYPES', set())
            }
            info.append(processor_info)
        
        return info


# Global processor registry instance
processor_registry = ProcessorRegistry()