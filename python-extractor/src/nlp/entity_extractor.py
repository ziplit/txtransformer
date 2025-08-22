"""
Specialized entity extraction with custom NER models and pattern matching
"""

import logging
import re
from typing import List, Dict, Any, Optional, Set, Tuple
from dataclasses import dataclass
from collections import defaultdict


@dataclass 
class EntityCandidate:
    """A candidate entity with confidence scoring"""
    text: str
    label: str
    confidence: float
    start_pos: int
    end_pos: int
    pattern_matched: str
    context_score: float = 0.0


class EntityExtractor:
    """Advanced entity extraction using pattern matching and contextual analysis"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Define comprehensive extraction patterns
        self.entity_patterns = self._initialize_patterns()
        
        # Context keywords for different entity types
        self.context_keywords = {
            'ORDER_ID': {
                'strong': ['order', 'order number', 'order id', 'reference', 'confirmation'],
                'weak': ['purchase', 'transaction', 'receipt', 'invoice']
            },
            'SKU': {
                'strong': ['sku', 'product code', 'item number', 'part number', 'model'],
                'weak': ['product', 'item', 'catalog', 'stock']  
            },
            'PRODUCT_NAME': {
                'strong': ['product', 'item', 'product name', 'item name'],
                'weak': ['description', 'title', 'merchandise', 'article']
            },
            'QUANTITY': {
                'strong': ['quantity', 'qty', 'amount', 'count', 'units'],
                'weak': ['pieces', 'items', 'each', 'total']
            }
        }
    
    def _initialize_patterns(self) -> Dict[str, List[Dict[str, Any]]]:
        """Initialize comprehensive entity extraction patterns"""
        patterns = {
            'ORDER_ID': [
                {
                    'pattern': r'\b(?:ORDER|ORD)[-_\s]*(\d{6,15})\b',
                    'confidence': 0.9,
                    'group': 1,
                    'case_sensitive': False
                },
                {
                    'pattern': r'\b([A-Z]{2,4}-\d{6,12})\b', 
                    'confidence': 0.85,
                    'group': 1,
                    'case_sensitive': True
                },
                {
                    'pattern': r'#(\d{8,15})\b',
                    'confidence': 0.8,
                    'group': 1,
                    'case_sensitive': False
                },
                {
                    'pattern': r'\b(\d{10,15})\b(?=\s*(?:order|purchase|confirmation))',
                    'confidence': 0.7,
                    'group': 1,
                    'case_sensitive': False
                }
            ],
            
            'SKU': [
                {
                    'pattern': r'\b(?:SKU|ITEM)[-_\s]*([A-Z0-9]{4,15})\b',
                    'confidence': 0.9,
                    'group': 1,
                    'case_sensitive': False
                },
                {
                    'pattern': r'\b([A-Z]{2,4}\d{4,10}[A-Z]?)\b',
                    'confidence': 0.8,
                    'group': 1,
                    'case_sensitive': True
                },
                {
                    'pattern': r'\b([A-Z0-9]{3,6}-[A-Z0-9]{2,8})\b',
                    'confidence': 0.85,
                    'group': 1,
                    'case_sensitive': True
                },
                {
                    'pattern': r'\b(PROD[-_]?[A-Z0-9]{4,12})\b',
                    'confidence': 0.75,
                    'group': 1,
                    'case_sensitive': True
                },
                {
                    'pattern': r'\b([A-Z]{3,8}\d{3,8}[A-Z]{0,3})\b',  # More flexible alphanumeric
                    'confidence': 0.6,
                    'group': 1,
                    'case_sensitive': True
                }
            ],
            
            'PRODUCT_NAME': [
                {
                    'pattern': r'(?:product|item)\s*[:]\s*([A-Za-z][A-Za-z\s\d&\'-]{5,60})',
                    'confidence': 0.8,
                    'group': 1,
                    'case_sensitive': False
                },
                {
                    'pattern': r'([A-Z][A-Za-z\s\d&\'-]{8,50})(?:\s*[-]\s*\$|\s+SKU|\s+Model)',
                    'confidence': 0.7,
                    'group': 1,
                    'case_sensitive': False
                },
                {
                    'pattern': r'([A-Za-z\s\d&\'-]{6,40})\s*\(\s*(?:SKU|Item|Model)',
                    'confidence': 0.75,
                    'group': 1,
                    'case_sensitive': False
                }
            ],
            
            'QUANTITY': [
                {
                    'pattern': r'(?:qty|quantity|amount|count)\s*[:=]\s*(\d{1,4})',
                    'confidence': 0.9,
                    'group': 1,
                    'case_sensitive': False
                },
                {
                    'pattern': r'(\d{1,4})\s*(?:pcs|pieces|units|items|each)',
                    'confidence': 0.85,
                    'group': 1,
                    'case_sensitive': False
                },
                {
                    'pattern': r'(\d{1,4})\s*x\s*[A-Za-z]',
                    'confidence': 0.8,
                    'group': 1,
                    'case_sensitive': False
                },
                {
                    'pattern': r'total\s*[:=]\s*(\d{1,4})\s*(?:items?|products?)',
                    'confidence': 0.75,
                    'group': 1,
                    'case_sensitive': False
                }
            ],
            
            'TRACKING_NUMBER': [
                {
                    'pattern': r'\b(1Z[0-9A-Z]{16})\b',  # UPS
                    'confidence': 0.95,
                    'group': 1,
                    'case_sensitive': True
                },
                {
                    'pattern': r'\b(\d{12})\b',  # FedEx
                    'confidence': 0.7,
                    'group': 1,
                    'case_sensitive': False
                },
                {
                    'pattern': r'\b(\d{20,22})\b',  # USPS
                    'confidence': 0.8,
                    'group': 1,
                    'case_sensitive': False
                },
                {
                    'pattern': r'(?:tracking|shipment)\s*[:]\s*([A-Z0-9]{8,25})',
                    'confidence': 0.85,
                    'group': 1,
                    'case_sensitive': False
                }
            ],
            
            'CUSTOMER_ID': [
                {
                    'pattern': r'\b(?:CUST|CUSTOMER)[-_\s]*(\d{6,12})\b',
                    'confidence': 0.9,
                    'group': 1,
                    'case_sensitive': False
                },
                {
                    'pattern': r'\b(C\d{6,12})\b',
                    'confidence': 0.8,
                    'group': 1,
                    'case_sensitive': True
                }
            ]
        }
        
        return patterns
    
    def extract_entities_by_type(self, text: str, entity_type: str, context: Optional[str] = None) -> List[EntityCandidate]:
        """
        Extract entities of a specific type from text
        
        Args:
            text: Text to search
            entity_type: Type of entity to extract (ORDER_ID, SKU, etc.)
            context: Additional context for scoring
            
        Returns:
            List of entity candidates sorted by confidence
        """
        if entity_type not in self.entity_patterns:
            self.logger.warning(f"Unknown entity type: {entity_type}")
            return []
        
        candidates = []
        patterns = self.entity_patterns[entity_type]
        
        for pattern_def in patterns:
            pattern = pattern_def['pattern']
            base_confidence = pattern_def['confidence']
            group = pattern_def.get('group', 0)
            case_sensitive = pattern_def.get('case_sensitive', False)
            
            flags = 0 if case_sensitive else re.IGNORECASE
            
            try:
                matches = re.finditer(pattern, text, flags)
                
                for match in matches:
                    extracted_text = match.group(group).strip()
                    
                    # Skip empty matches, but allow single characters for quantities
                    if len(extracted_text) == 0:
                        continue
                    if len(extracted_text) == 1 and entity_type != 'QUANTITY':
                        continue
                    
                    # Calculate context-adjusted confidence
                    context_score = self._calculate_context_score(entity_type, text, match.start(), context)
                    final_confidence = min(base_confidence + context_score, 1.0)
                    
                    candidate = EntityCandidate(
                        text=extracted_text,
                        label=entity_type,
                        confidence=final_confidence,
                        start_pos=match.start(group),
                        end_pos=match.end(group),
                        pattern_matched=pattern,
                        context_score=context_score
                    )
                    
                    candidates.append(candidate)
                    
            except re.error as e:
                self.logger.error(f"Invalid regex pattern for {entity_type}: {pattern} - {e}")
                continue
        
        # Remove duplicates and sort by confidence
        candidates = self._deduplicate_candidates(candidates)
        candidates.sort(key=lambda x: x.confidence, reverse=True)
        
        return candidates
    
    def _calculate_context_score(self, entity_type: str, text: str, position: int, context: Optional[str]) -> float:
        """Calculate context-based confidence adjustment"""
        score = 0.0
        
        # Get surrounding text (±100 characters)
        start = max(0, position - 100)
        end = min(len(text), position + 100)
        surrounding = text[start:end].lower()
        
        # Check for context keywords
        if entity_type in self.context_keywords:
            keywords = self.context_keywords[entity_type]
            
            # Strong context keywords
            for keyword in keywords['strong']:
                if keyword in surrounding:
                    score += 0.15
                    break
            
            # Weak context keywords  
            for keyword in keywords['weak']:
                if keyword in surrounding:
                    score += 0.05
                    break
        
        # Additional context from external context parameter
        if context:
            context_lower = context.lower()
            if entity_type in self.context_keywords:
                keywords = self.context_keywords[entity_type]
                
                for keyword in keywords['strong']:
                    if keyword in context_lower:
                        score += 0.1
                        break
                
                for keyword in keywords['weak']:
                    if keyword in context_lower:
                        score += 0.03
                        break
        
        return min(score, 0.3)  # Cap context bonus
    
    def _deduplicate_candidates(self, candidates: List[EntityCandidate]) -> List[EntityCandidate]:
        """Remove duplicate candidates, keeping the highest confidence version"""
        if not candidates:
            return []
        
        # Group by text content
        groups = defaultdict(list)
        for candidate in candidates:
            # Use normalized text as key to catch minor variations
            key = candidate.text.lower().strip()
            groups[key].append(candidate)
        
        # Keep best candidate from each group
        deduplicated = []
        for group in groups.values():
            best_candidate = max(group, key=lambda x: x.confidence)
            deduplicated.append(best_candidate)
        
        return deduplicated
    
    def extract_all_entities(self, text: str, context: Optional[str] = None) -> Dict[str, List[EntityCandidate]]:
        """
        Extract all supported entity types from text
        
        Args:
            text: Text to analyze
            context: Additional context
            
        Returns:
            Dictionary mapping entity types to lists of candidates
        """
        results = {}
        
        for entity_type in self.entity_patterns.keys():
            candidates = self.extract_entities_by_type(text, entity_type, context)
            if candidates:  # Only include types with results
                results[entity_type] = candidates
        
        return results
    
    def get_best_entities(self, text: str, context: Optional[str] = None, min_confidence: float = 0.5) -> Dict[str, EntityCandidate]:
        """
        Get the best (highest confidence) entity of each type
        
        Args:
            text: Text to analyze
            context: Additional context
            min_confidence: Minimum confidence threshold
            
        Returns:
            Dictionary mapping entity types to best candidates
        """
        all_entities = self.extract_all_entities(text, context)
        best_entities = {}
        
        for entity_type, candidates in all_entities.items():
            if candidates and candidates[0].confidence >= min_confidence:
                best_entities[entity_type] = candidates[0]
        
        return best_entities
    
    def validate_entity(self, text: str, entity_type: str) -> Dict[str, Any]:
        """
        Validate if a given text matches patterns for an entity type
        
        Args:
            text: Text to validate
            entity_type: Entity type to validate against
            
        Returns:
            Validation result with score and details
        """
        if entity_type not in self.entity_patterns:
            return {'valid': False, 'reason': 'Unknown entity type'}
        
        patterns = self.entity_patterns[entity_type]
        best_match = None
        best_confidence = 0.0
        
        for pattern_def in patterns:
            pattern = pattern_def['pattern']
            case_sensitive = pattern_def.get('case_sensitive', False)
            flags = 0 if case_sensitive else re.IGNORECASE
            
            try:
                if re.fullmatch(pattern, text, flags):
                    confidence = pattern_def['confidence']
                    if confidence > best_confidence:
                        best_confidence = confidence
                        best_match = pattern
            except re.error:
                continue
        
        return {
            'valid': best_match is not None,
            'confidence': best_confidence,
            'matched_pattern': best_match,
            'entity_type': entity_type
        }
    
    def get_extraction_stats(self, text: str, context: Optional[str] = None) -> Dict[str, Any]:
        """Get comprehensive statistics about entity extraction"""
        all_entities = self.extract_all_entities(text, context)
        
        stats = {
            'total_entities_found': sum(len(candidates) for candidates in all_entities.values()),
            'entity_types_found': len(all_entities),
            'entities_by_type': {
                entity_type: len(candidates) 
                for entity_type, candidates in all_entities.items()
            },
            'high_confidence_entities': sum(
                1 for candidates in all_entities.values() 
                for candidate in candidates 
                if candidate.confidence > 0.8
            ),
            'average_confidence_by_type': {
                entity_type: sum(c.confidence for c in candidates) / len(candidates)
                for entity_type, candidates in all_entities.items()
            }
        }
        
        return stats