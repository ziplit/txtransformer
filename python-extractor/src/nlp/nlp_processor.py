"""
Main NLP processor for named entity recognition and text analysis
"""

import logging
import spacy
from typing import List, Dict, Any, Optional, Union, Tuple
from dataclasses import dataclass, field
from spacy.lang.en import English
from spacy.matcher import Matcher, PhraseMatcher
from spacy.tokens import Doc, Span
import re


@dataclass
class ExtractedEntity:
    """Structured representation of an extracted entity"""
    text: str
    label: str
    confidence: float
    start_char: int
    end_char: int
    context: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class NLPProcessor:
    """Main NLP processor using spaCy for named entity recognition"""
    
    def __init__(self, model_name: str = "en_core_web_sm"):
        self.logger = logging.getLogger(__name__)
        self.model_name = model_name
        self.nlp = None
        self._initialize_nlp_pipeline()
        
        # Entity types we'll extract
        self.custom_entity_types = {
            'ORDER_ID', 'SKU', 'PRODUCT_NAME', 'QUANTITY', 
            'TRACKING_NUMBER', 'INVOICE_ID', 'CUSTOMER_ID'
        }
    
    def _initialize_nlp_pipeline(self):
        """Initialize spaCy NLP pipeline with custom components"""
        try:
            self.nlp = spacy.load(self.model_name)
            self.logger.info(f"Loaded spaCy model: {self.model_name}")
            
            # Add custom pipeline components
            self._add_custom_components()
            
        except OSError as e:
            self.logger.error(f"Failed to load spaCy model {self.model_name}: {e}")
            # Fallback to blank English model
            try:
                self.nlp = English()
                self.logger.warning("Using blank English model as fallback")
            except Exception as fallback_error:
                self.logger.error(f"Failed to create fallback model: {fallback_error}")
                raise
    
    def _add_custom_components(self):
        """Add custom NLP components to the pipeline"""
        # Add custom entity ruler for structured patterns
        if "entity_ruler" not in self.nlp.pipe_names:
            ruler = self.nlp.add_pipe("entity_ruler", before="ner")
            patterns = self._get_entity_patterns()
            ruler.add_patterns(patterns)
            self.logger.info(f"Added {len(patterns)} entity patterns")
    
    def _get_entity_patterns(self) -> List[Dict[str, Any]]:
        """Define patterns for custom entity recognition"""
        patterns = []
        
        # ORDER_ID patterns
        order_patterns = [
            {"label": "ORDER_ID", "pattern": [{"TEXT": {"REGEX": r"^(ORD|ORDER)[-_]?\d{6,12}$"}}]},
            {"label": "ORDER_ID", "pattern": [{"TEXT": {"REGEX": r"^#?\d{8,12}$"}}]},
            {"label": "ORDER_ID", "pattern": [{"TEXT": {"REGEX": r"^[A-Z]{2,3}-\d{6,10}$"}}]},
        ]
        
        # SKU patterns
        sku_patterns = [
            {"label": "SKU", "pattern": [{"TEXT": {"REGEX": r"^[A-Z0-9]{3,}-[A-Z0-9]{2,}$"}}]},
            {"label": "SKU", "pattern": [{"TEXT": {"REGEX": r"^(SKU|ITEM)[-_]?[A-Z0-9]{4,12}$"}}]},
            {"label": "SKU", "pattern": [{"TEXT": {"REGEX": r"^[A-Z]{2,4}\d{4,8}[A-Z]?$"}}]},
        ]
        
        # TRACKING_NUMBER patterns
        tracking_patterns = [
            {"label": "TRACKING_NUMBER", "pattern": [{"TEXT": {"REGEX": r"^1Z[0-9A-Z]{16}$"}}]},  # UPS
            {"label": "TRACKING_NUMBER", "pattern": [{"TEXT": {"REGEX": r"^\d{12}$"}}]},  # FedEx
            {"label": "TRACKING_NUMBER", "pattern": [{"TEXT": {"REGEX": r"^\d{20,22}$"}}]},  # USPS
        ]
        
        # QUANTITY patterns (with context)
        quantity_patterns = [
            {"label": "QUANTITY", "pattern": [
                {"LOWER": {"IN": ["qty", "quantity", "amount", "count"]}},
                {"TEXT": ":"},
                {"TEXT": {"REGEX": r"^\d+$"}}
            ]},
            {"label": "QUANTITY", "pattern": [
                {"TEXT": {"REGEX": r"^\d+$"}},
                {"LOWER": {"IN": ["pcs", "pieces", "units", "items", "each"]}}
            ]},
        ]
        
        # INVOICE_ID patterns  
        invoice_patterns = [
            {"label": "INVOICE_ID", "pattern": [{"TEXT": {"REGEX": r"^(INV|INVOICE)[-_]?\d{6,12}$"}}]},
            {"label": "INVOICE_ID", "pattern": [{"TEXT": {"REGEX": r"^#?\d{6,10}$"}}]},
        ]
        
        # CUSTOMER_ID patterns
        customer_patterns = [
            {"label": "CUSTOMER_ID", "pattern": [{"TEXT": {"REGEX": r"^(CUST|CUSTOMER)[-_]?\d{6,12}$"}}]},
            {"label": "CUSTOMER_ID", "pattern": [{"TEXT": {"REGEX": r"^C\d{6,10}$"}}]},
        ]
        
        patterns.extend(order_patterns)
        patterns.extend(sku_patterns)
        patterns.extend(tracking_patterns)
        patterns.extend(quantity_patterns)
        patterns.extend(invoice_patterns)
        patterns.extend(customer_patterns)
        
        return patterns
    
    def extract_entities(self, text: str, context: Optional[str] = None) -> List[ExtractedEntity]:
        """
        Extract named entities from text using spaCy NLP pipeline
        
        Args:
            text: Text to analyze
            context: Additional context for entity extraction
            
        Returns:
            List of extracted entities with confidence scores
        """
        if not self.nlp:
            self.logger.error("NLP pipeline not initialized")
            return []
        
        try:
            entities = []
            
            # Process text with spaCy
            doc = self.nlp(text)
            
            # Extract standard named entities
            for ent in doc.ents:
                confidence = self._calculate_entity_confidence(ent, doc, context)
                
                entity = ExtractedEntity(
                    text=ent.text,
                    label=ent.label_,
                    confidence=confidence,
                    start_char=ent.start_char,
                    end_char=ent.end_char,
                    context=context,
                    metadata={
                        'spacy_confidence': getattr(ent, 'confidence', None),
                        'entity_id': ent.ent_id_,
                        'kb_id': ent.kb_id_
                    }
                )
                
                entities.append(entity)
            
            # Add rule-based entity extraction
            rule_entities = self._extract_rule_based_entities(text, doc, context)
            entities.extend(rule_entities)
            
            # Sort by confidence
            entities.sort(key=lambda x: x.confidence, reverse=True)
            
            self.logger.debug(f"Extracted {len(entities)} entities from text")
            return entities
            
        except Exception as e:
            self.logger.error(f"Entity extraction failed: {e}")
            return []
    
    def _calculate_entity_confidence(self, ent: Span, doc: Doc, context: Optional[str]) -> float:
        """Calculate confidence score for an extracted entity"""
        confidence = 0.6  # Base confidence for spaCy entities
        
        # Adjust based on entity type
        entity_type_bonuses = {
            'PERSON': 0.2,
            'ORG': 0.15,
            'MONEY': 0.25,
            'PRODUCT': 0.2,
            'CARDINAL': 0.1,
            'ORDER_ID': 0.3,
            'SKU': 0.25,
            'TRACKING_NUMBER': 0.35,
            'QUANTITY': 0.2
        }
        
        confidence += entity_type_bonuses.get(ent.label_, 0.05)
        
        # Length bonus (longer entities are often more reliable)
        if len(ent.text) > 5:
            confidence += 0.1
        elif len(ent.text) > 10:
            confidence += 0.15
        
        # Context bonus
        if context and self._has_relevant_context(ent.label_, context):
            confidence += 0.1
        
        # Penalty for very short entities
        if len(ent.text) < 3:
            confidence -= 0.2
        
        # Pattern recognition bonus
        if self._matches_expected_pattern(ent.text, ent.label_):
            confidence += 0.15
        
        return min(confidence, 1.0)
    
    def _has_relevant_context(self, entity_label: str, context: str) -> bool:
        """Check if context is relevant for the entity type"""
        context_keywords = {
            'ORDER_ID': ['order', 'purchase', 'transaction', 'receipt'],
            'SKU': ['product', 'item', 'catalog', 'stock'],
            'TRACKING_NUMBER': ['shipping', 'delivery', 'tracking', 'shipment'],
            'QUANTITY': ['quantity', 'amount', 'count', 'units'],
            'PRODUCT': ['product', 'item', 'merchandise'],
            'MONEY': ['price', 'cost', 'amount', 'total']
        }
        
        keywords = context_keywords.get(entity_label, [])
        return any(keyword in context.lower() for keyword in keywords)
    
    def _matches_expected_pattern(self, text: str, label: str) -> bool:
        """Check if entity text matches expected patterns for the label"""
        pattern_checks = {
            'ORDER_ID': lambda t: bool(re.match(r'^(ORD|ORDER)?[-_]?\d{6,}|\#?\d{8,}|[A-Z]{2,3}-\d{6,}$', t, re.I)),
            'SKU': lambda t: bool(re.match(r'^[A-Z0-9]{3,}-[A-Z0-9]{2,}|(SKU|ITEM)[-_]?[A-Z0-9]{4,}|[A-Z]{2,4}\d{4,8}[A-Z]?$', t, re.I)),
            'TRACKING_NUMBER': lambda t: bool(re.match(r'^1Z[0-9A-Z]{16}|\d{12}|\d{20,22}$', t)),
            'MONEY': lambda t: bool(re.search(r'[\$€£¥]\d+|\d+\.\d{2}', t)),
            'CARDINAL': lambda t: t.isdigit()
        }
        
        checker = pattern_checks.get(label)
        if checker:
            return checker(text)
        return True  # No specific pattern check for this label
    
    def _extract_rule_based_entities(self, text: str, doc: Doc, context: Optional[str]) -> List[ExtractedEntity]:
        """Extract entities using rule-based patterns"""
        entities = []
        
        # Product name extraction (more sophisticated)
        product_entities = self._extract_product_names(text, doc, context)
        entities.extend(product_entities)
        
        # Quantity extraction with better context awareness
        quantity_entities = self._extract_quantities_with_context(text, doc, context)
        entities.extend(quantity_entities)
        
        return entities
    
    def _extract_product_names(self, text: str, doc: Doc, context: Optional[str]) -> List[ExtractedEntity]:
        """Extract product names using linguistic patterns"""
        entities = []
        
        # Look for patterns like "Product: [Name]", "Item: [Name]"
        product_patterns = [
            r'(?i)(?:product|item|article|merchandise)[:,\s]+([A-Za-z][A-Za-z\s\d-]{3,50})',
            r'(?i)([A-Z][A-Za-z\s\d-]{10,50})(?:\s+[-]?\s*\$\d+|\s+SKU)',  # Product followed by price/SKU
        ]
        
        for pattern in product_patterns:
            matches = re.finditer(pattern, text)
            for match in matches:
                product_name = match.group(1).strip()
                if len(product_name) > 3 and not product_name.isdigit():
                    confidence = 0.4 + (0.1 if len(product_name) > 10 else 0)
                    if context and 'product' in context.lower():
                        confidence += 0.15
                    
                    entities.append(ExtractedEntity(
                        text=product_name,
                        label='PRODUCT_NAME',
                        confidence=min(confidence, 0.85),
                        start_char=match.start(1),
                        end_char=match.end(1),
                        context=context,
                        metadata={'extraction_method': 'rule_based_product'}
                    ))
        
        return entities
    
    def _extract_quantities_with_context(self, text: str, doc: Doc, context: Optional[str]) -> List[ExtractedEntity]:
        """Extract quantities with contextual awareness"""
        entities = []
        
        # Patterns for quantity extraction
        quantity_patterns = [
            r'(?i)(?:qty|quantity|amount|count)[:,\s]*(\d+)',
            r'(?i)(\d+)\s*(?:pcs|pieces|units|items|each)',
            r'(?i)(\d+)\s*x\s*[A-Za-z]',  # "5 x Product"
        ]
        
        for pattern in quantity_patterns:
            matches = re.finditer(pattern, text)
            for match in matches:
                quantity = match.group(1)
                if quantity.isdigit() and 1 <= int(quantity) <= 10000:  # Reasonable quantity range
                    confidence = 0.5
                    if context and any(word in context.lower() for word in ['order', 'purchase', 'buy']):
                        confidence += 0.2
                    
                    entities.append(ExtractedEntity(
                        text=quantity,
                        label='QUANTITY',
                        confidence=min(confidence, 0.9),
                        start_char=match.start(1),
                        end_char=match.end(1),
                        context=context,
                        metadata={'extraction_method': 'rule_based_quantity'}
                    ))
        
        return entities
    
    def extract_product_information(self, text: str, context: Optional[str] = None) -> Dict[str, Any]:
        """
        Extract comprehensive product information from text
        
        Args:
            text: Text to analyze
            context: Additional context
            
        Returns:
            Dictionary with extracted product information
        """
        entities = self.extract_entities(text, context)
        
        # Group entities by type
        grouped_entities = {}
        for entity in entities:
            if entity.label not in grouped_entities:
                grouped_entities[entity.label] = []
            grouped_entities[entity.label].append(entity)
        
        # Extract the most confident entity of each type
        product_info = {}
        for label, entity_list in grouped_entities.items():
            if entity_list:
                best_entity = max(entity_list, key=lambda x: x.confidence)
                product_info[label.lower()] = {
                    'value': best_entity.text,
                    'confidence': best_entity.confidence,
                    'start_char': best_entity.start_char,
                    'end_char': best_entity.end_char
                }
        
        return product_info
    
    def get_processing_stats(self) -> Dict[str, Any]:
        """Get statistics about the NLP processor"""
        return {
            'model_name': self.model_name,
            'pipeline_components': list(self.nlp.pipe_names) if self.nlp else [],
            'custom_entity_types': list(self.custom_entity_types),
            'model_loaded': self.nlp is not None
        }