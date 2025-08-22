"""
Base processor class for document processing
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from pathlib import Path

from ..config import settings


@dataclass
class ProcessingResult:
    """Result of document processing"""
    success: bool
    elements: List[Dict[str, Any]]
    metadata: Dict[str, Any]
    error: Optional[str] = None
    processing_time_ms: Optional[float] = None


@dataclass
class ProcessingContext:
    """Context for document processing"""
    file_path: Optional[Path] = None
    file_content: Optional[bytes] = None
    filename: Optional[str] = None
    mime_type: Optional[str] = None
    options: Optional[Dict[str, Any]] = None


class BaseProcessor(ABC):
    """Base class for all document processors"""
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        
    @abstractmethod
    def can_process(self, context: ProcessingContext) -> bool:
        """Check if this processor can handle the given content"""
        pass
    
    @abstractmethod
    async def process(self, context: ProcessingContext) -> ProcessingResult:
        """Process the document and return structured elements"""
        pass
    
    def _create_success_result(
        self, 
        elements: List[Dict[str, Any]], 
        metadata: Dict[str, Any] = None,
        processing_time_ms: float = None
    ) -> ProcessingResult:
        """Helper to create successful processing result"""
        return ProcessingResult(
            success=True,
            elements=elements,
            metadata=metadata or {},
            processing_time_ms=processing_time_ms
        )
    
    def _create_error_result(self, error: str) -> ProcessingResult:
        """Helper to create error processing result"""
        return ProcessingResult(
            success=False,
            elements=[],
            metadata={},
            error=error
        )
    
    def _sanitize_text(self, text: str) -> str:
        """Sanitize extracted text"""
        if not text:
            return ""
        
        # Remove excessive whitespace
        text = " ".join(text.split())
        
        # Remove control characters except newlines and tabs
        text = "".join(char for char in text if ord(char) >= 32 or char in '\n\t')
        
        return text.strip()
    
    def _extract_metadata(self, element: Dict[str, Any]) -> Dict[str, Any]:
        """Extract metadata from unstructured element"""
        metadata = {}
        
        if hasattr(element, 'metadata') and element.metadata:
            metadata.update(element.metadata.to_dict())
        elif isinstance(element, dict) and 'metadata' in element:
            metadata.update(element['metadata'])
        
        return metadata