"""
Rule-based matchers for structured data extraction using spaCy
"""

import logging
import spacy
from typing import List, Dict, Any, Optional, Union
from spacy.matcher import Matcher, PhraseMatcher
from spacy.tokens import Doc, Span
from dataclasses import dataclass


@dataclass
class MatchResult:
    """Result from rule-based matching"""
    text: str
    label: str
    start: int
    end: int
    confidence: float
    rule_id: str
    matched_tokens: List[str]


class RuleMatchers:
    """Advanced rule-based matching using spaCy's Matcher and PhraseMatcher"""
    
    def __init__(self, nlp_model):
        self.logger = logging.getLogger(__name__)
        self.nlp = nlp_model
        
        # Initialize matchers
        self.matcher = Matcher(nlp_model.vocab)
        self.phrase_matcher = PhraseMatcher(nlp_model.vocab)
        
        # Initialize rule sets
        self._setup_token_matchers()
        self._setup_phrase_matchers()
    
    def _setup_token_matchers(self):
        """Set up token-based matching rules"""
        
        # Order ID patterns
        order_patterns = [
            [{"TEXT": {"REGEX": r"^(ORDER|ORD)$"}, "OP": "?"}, 
             {"TEXT": {"REGEX": r"^[-_#]?$"}, "OP": "?"}, 
             {"TEXT": {"REGEX": r"^\d{6,15}$"}}],
            
            [{"TEXT": {"REGEX": r"^[A-Z]{2,4}$"}}, 
             {"TEXT": "-"}, 
             {"TEXT": {"REGEX": r"^\d{6,12}$"}}],
            
            [{"TEXT": "#"}, 
             {"TEXT": {"REGEX": r"^\d{8,15}$"}}]
        ]
        
        for i, pattern in enumerate(order_patterns):
            self.matcher.add(f"ORDER_ID_{i}", [pattern])
        
        # SKU patterns
        sku_patterns = [
            [{"TEXT": {"REGEX": r"^(SKU|ITEM)$"}, "OP": "?"}, 
             {"TEXT": {"REGEX": r"^[-_:]?$"}, "OP": "?"}, 
             {"TEXT": {"REGEX": r"^[A-Z0-9]{4,15}$"}}],
            
            [{"TEXT": {"REGEX": r"^[A-Z]{2,4}\d{4,10}[A-Z]?$"}}],
            
            [{"TEXT": {"REGEX": r"^[A-Z0-9]{3,6}$"}}, 
             {"TEXT": "-"}, 
             {"TEXT": {"REGEX": r"^[A-Z0-9]{2,8}$"}}]
        ]
        
        for i, pattern in enumerate(sku_patterns):
            self.matcher.add(f"SKU_{i}", [pattern])
        
        # Quantity patterns
        quantity_patterns = [
            [{"LOWER": {"IN": ["qty", "quantity", "amount", "count"]}}, 
             {"TEXT": ":"}, 
             {"TEXT": {"REGEX": r"^\d{1,4}$"}}],
            
            [{"TEXT": {"REGEX": r"^\d{1,4}$"}}, 
             {"LOWER": {"IN": ["pcs", "pieces", "units", "items", "each"]}}],
            
            [{"TEXT": {"REGEX": r"^\d{1,4}$"}}, 
             {"TEXT": "x"}, 
             {"POS": "NOUN"}]
        ]
        
        for i, pattern in enumerate(quantity_patterns):
            self.matcher.add(f"QUANTITY_{i}", [pattern])
        
        # Tracking number patterns
        tracking_patterns = [
            [{"LOWER": {"IN": ["tracking", "shipment", "delivery"]}}, 
             {"TEXT": ":"}, 
             {"TEXT": {"REGEX": r"^[A-Z0-9]{8,25}$"}}],
            
            [{"TEXT": {"REGEX": r"^1Z[0-9A-Z]{16}$"}}],  # UPS
            
            [{"TEXT": {"REGEX": r"^\d{20,22}$"}}]  # USPS long format
        ]
        
        for i, pattern in enumerate(tracking_patterns):
            self.matcher.add(f"TRACKING_{i}", [pattern])
        
        # Product name patterns (more complex)
        product_patterns = [
            [{"LOWER": {"IN": ["product", "item"]}}, 
             {"TEXT": ":"}, 
             {"POS": {"IN": ["NOUN", "PROPN"]}, "OP": "+"}, 
             {"POS": {"IN": ["NOUN", "ADJ"]}, "OP": "*"}],
            
            [{"POS": "PROPN", "OP": "+"}, 
             {"TEXT": "-"}, 
             {"TEXT": "$", "OP": "!"}],  # Brand - Model (not followed by price)
        ]
        
        for i, pattern in enumerate(product_patterns):
            self.matcher.add(f"PRODUCT_{i}", [pattern])
        
        self.logger.info(f"Initialized token matcher with {len(self.matcher)} patterns")
    
    def _setup_phrase_matchers(self):
        """Set up phrase-based matching rules"""
        
        # Common order-related phrases
        order_phrases = [
            "Order Number", "Order ID", "Purchase Order", "Order Reference",
            "Confirmation Number", "Transaction ID", "Receipt Number"
        ]
        
        # Common product-related phrases  
        product_phrases = [
            "Product Name", "Item Description", "Product Title",
            "Article Name", "Merchandise Description"
        ]
        
        # Common quantity-related phrases
        quantity_phrases = [
            "Quantity Ordered", "Items Purchased", "Total Quantity",
            "Units Ordered", "Pieces Ordered"
        ]
        
        # Convert phrases to Doc objects and add to phrase matcher
        order_patterns = [self.nlp(phrase) for phrase in order_phrases]
        product_patterns = [self.nlp(phrase) for phrase in product_phrases]
        quantity_patterns = [self.nlp(phrase) for phrase in quantity_phrases]
        
        self.phrase_matcher.add("ORDER_PHRASE", order_patterns)
        self.phrase_matcher.add("PRODUCT_PHRASE", product_patterns)
        self.phrase_matcher.add("QUANTITY_PHRASE", quantity_patterns)
        
        self.logger.info(f"Initialized phrase matcher with {len(order_phrases + product_phrases + quantity_phrases)} phrases")
    
    def find_matches(self, text: str) -> List[MatchResult]:
        """
        Find all rule-based matches in text
        
        Args:
            text: Text to analyze
            
        Returns:
            List of match results sorted by confidence
        """
        if not self.nlp:
            self.logger.error("NLP model not available for rule matching")
            return []
        
        try:
            doc = self.nlp(text)
            matches = []
            
            # Token-based matches
            token_matches = self.matcher(doc)
            for match_id, start, end in token_matches:
                span = doc[start:end]
                rule_id = self.nlp.vocab.strings[match_id]
                
                # Determine entity type and confidence based on rule
                entity_type, confidence = self._get_entity_type_and_confidence(rule_id, span)
                
                match_result = MatchResult(
                    text=span.text,
                    label=entity_type,
                    start=span.start_char,
                    end=span.end_char,
                    confidence=confidence,
                    rule_id=rule_id,
                    matched_tokens=[token.text for token in span]
                )
                
                matches.append(match_result)
            
            # Phrase-based matches
            phrase_matches = self.phrase_matcher(doc)
            for match_id, start, end in phrase_matches:
                span = doc[start:end]
                rule_id = self.nlp.vocab.strings[match_id]
                
                # For phrase matches, we need to look for the actual value nearby
                value_span = self._find_associated_value(doc, span, rule_id)
                if value_span:
                    entity_type = rule_id.replace("_PHRASE", "")
                    
                    match_result = MatchResult(
                        text=value_span.text,
                        label=entity_type,
                        start=value_span.start_char,
                        end=value_span.end_char,
                        confidence=0.7,  # Lower confidence for phrase-based matches
                        rule_id=f"PHRASE_{rule_id}",
                        matched_tokens=[token.text for token in value_span]
                    )
                    
                    matches.append(match_result)
            
            # Sort by confidence and remove duplicates
            matches = self._deduplicate_matches(matches)
            matches.sort(key=lambda x: x.confidence, reverse=True)
            
            self.logger.debug(f"Found {len(matches)} rule-based matches")
            return matches
            
        except Exception as e:
            self.logger.error(f"Rule matching failed: {e}")
            return []
    
    def _get_entity_type_and_confidence(self, rule_id: str, span: Span) -> tuple[str, float]:
        """Determine entity type and confidence from rule ID and span"""
        
        # Parse rule ID to get entity type
        if rule_id.startswith("ORDER_ID"):
            return "ORDER_ID", 0.85
        elif rule_id.startswith("SKU"):
            return "SKU", 0.8
        elif rule_id.startswith("QUANTITY"):
            return "QUANTITY", 0.75
        elif rule_id.startswith("TRACKING"):
            return "TRACKING_NUMBER", 0.9
        elif rule_id.startswith("PRODUCT"):
            return "PRODUCT_NAME", 0.6
        else:
            return "UNKNOWN", 0.5
    
    def _find_associated_value(self, doc: Doc, phrase_span: Span, phrase_type: str) -> Optional[Span]:
        """Find the value associated with a phrase match"""
        
        # Look for patterns like "Order Number: 12345" or "Order Number 12345"
        # Check the next few tokens after the phrase
        start_idx = phrase_span.end
        end_idx = min(len(doc), start_idx + 5)  # Look ahead up to 5 tokens
        
        for i in range(start_idx, end_idx):
            token = doc[i]
            
            # Skip punctuation and whitespace
            if token.text in [":", "-", "="] or token.is_space:
                continue
            
            # Look for appropriate value based on phrase type
            if phrase_type == "ORDER_PHRASE":
                if token.like_num or (token.text.isalnum() and len(token.text) >= 6):
                    return doc[i:i+1]
            elif phrase_type == "PRODUCT_PHRASE":
                # For products, take multiple tokens until we hit a delimiter
                end_token = i
                while end_token < len(doc) and not doc[end_token].text in [".", ",", ";", "\n"]:
                    end_token += 1
                if end_token > i:
                    return doc[i:end_token]
            elif phrase_type == "QUANTITY_PHRASE":
                if token.like_num:
                    return doc[i:i+1]
        
        return None
    
    def _deduplicate_matches(self, matches: List[MatchResult]) -> List[MatchResult]:
        """Remove overlapping and duplicate matches"""
        if not matches:
            return []
        
        # Sort by start position
        matches.sort(key=lambda x: (x.start, -x.confidence))
        
        deduplicated = []
        for match in matches:
            # Check if this match overlaps with any already added match
            overlaps = False
            for existing in deduplicated:
                if (match.start < existing.end and match.end > existing.start):
                    overlaps = True
                    break
            
            if not overlaps:
                deduplicated.append(match)
        
        return deduplicated
    
    def find_matches_by_type(self, text: str, entity_type: str) -> List[MatchResult]:
        """Find matches of a specific entity type"""
        all_matches = self.find_matches(text)
        return [match for match in all_matches if match.label == entity_type]
    
    def add_custom_pattern(self, pattern_name: str, token_pattern: List[Dict], entity_type: str):
        """
        Add a custom token pattern to the matcher
        
        Args:
            pattern_name: Unique name for the pattern
            token_pattern: spaCy token pattern specification
            entity_type: Entity type to assign to matches
        """
        try:
            self.matcher.add(pattern_name, [token_pattern])
            self.logger.info(f"Added custom pattern '{pattern_name}' for entity type '{entity_type}'")
        except Exception as e:
            self.logger.error(f"Failed to add custom pattern '{pattern_name}': {e}")
    
    def add_custom_phrases(self, phrase_name: str, phrases: List[str]):
        """
        Add custom phrases to the phrase matcher
        
        Args:
            phrase_name: Unique name for the phrase set
            phrases: List of phrases to match
        """
        try:
            phrase_patterns = [self.nlp(phrase) for phrase in phrases]
            self.phrase_matcher.add(phrase_name, phrase_patterns)
            self.logger.info(f"Added {len(phrases)} custom phrases under '{phrase_name}'")
        except Exception as e:
            self.logger.error(f"Failed to add custom phrases '{phrase_name}': {e}")
    
    def get_matcher_stats(self) -> Dict[str, Any]:
        """Get statistics about configured matchers"""
        # Get available labels from matcher vocabulary strings
        available_labels = []
        try:
            # Try to get pattern names from matcher internals
            if hasattr(self.matcher, '_patterns'):
                pattern_ids = self.matcher._patterns.keys()
                available_labels = list(set(
                    self.nlp.vocab.strings[pattern_id].split('_')[0] 
                    for pattern_id in pattern_ids
                ))
        except (AttributeError, KeyError):
            # Fallback to manual list based on what we added
            available_labels = ['ORDER', 'SKU', 'QUANTITY', 'TRACKING', 'PRODUCT']
        
        return {
            'token_patterns': len(self.matcher),
            'phrase_patterns': len(self.phrase_matcher),
            'available_labels': available_labels
        }