"""
Pattern-based extraction for common structured fields like Order IDs, SKUs, phone numbers, emails
"""

import logging
import re
from typing import Dict, List, Any, Optional, Union, Pattern
from dataclasses import dataclass


@dataclass
class ExtractedPattern:
    """Structured pattern match representation"""
    raw_text: str
    pattern_type: str
    confidence: float
    value: str
    context: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class PatternExtractor:
    """Pattern-based extraction for structured fields"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Compile all patterns at initialization for performance
        self.patterns = self._initialize_patterns()
        
        # Context indicators for different field types
        self.context_indicators = {
            'order_id': [
                'order', 'order number', 'order #', 'order id', 'purchase order',
                'po number', 'po #', 'transaction', 'reference', 'confirmation'
            ],
            'sku': [
                'sku', 'item number', 'product code', 'part number', 'catalog',
                'model', 'item code', 'product id', 'part #'
            ],
            'email': [
                'email', 'e-mail', 'contact', 'from', 'to', 'reply', '@'
            ],
            'phone': [
                'phone', 'tel', 'telephone', 'mobile', 'cell', 'call', 'contact'
            ],
            'tracking': [
                'tracking', 'tracking number', 'shipment', 'carrier', 'ups', 'fedex', 'usps'
            ],
            'invoice': [
                'invoice', 'invoice number', 'invoice #', 'bill', 'billing'
            ],
            'customer_id': [
                'customer', 'customer id', 'customer number', 'account', 'client id'
            ]
        }
    
    def _initialize_patterns(self) -> Dict[str, Dict]:
        """Initialize all regex patterns with metadata"""
        return {
            'order_id': {
                'patterns': [
                    re.compile(r'\b([A-Z]{2,4}-?\d{6,12})\b'),  # ABC-123456789
                    re.compile(r'\b(ORD-?\d{6,10})\b', re.IGNORECASE),  # ORD123456
                    re.compile(r'\b([0-9]{8,15})\b'),  # Long number sequences
                    re.compile(r'\b([A-Z]+\d{6,})\b'),  # Letters followed by numbers
                    re.compile(r'\b(\d{3}-\d{3}-\d{4,6})\b'),  # 123-456-7890
                ],
                'confidence_base': 0.6,
                'context_boost': 0.3,
                'format_validators': [
                    lambda x: len(x) >= 6,
                    lambda x: any(c.isdigit() for c in x)
                ]
            },
            
            'sku': {
                'patterns': [
                    re.compile(r'\b([A-Z]{2,5}\d{2,8}[A-Z]?)\b'),  # ABC123A
                    re.compile(r'\b(\d{4,}-[A-Z0-9]{2,8})\b'),  # 1234-ABC5
                    re.compile(r'\b([A-Z]+[-_]\d+[-_]?[A-Z]*)\b'),  # PROD-123-A
                    re.compile(r'\b(\d{6,12})\b'),  # Long product numbers
                    re.compile(r'\b([A-Z]{1,3}\d{2,6}[A-Z]{0,3})\b'),  # A123B
                ],
                'confidence_base': 0.5,
                'context_boost': 0.3,
                'format_validators': [
                    lambda x: len(x) >= 4,
                    lambda x: any(c.isdigit() for c in x),
                    lambda x: any(c.isalpha() for c in x)
                ]
            },
            
            'email': {
                'patterns': [
                    re.compile(r'\b([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})\b'),
                ],
                'confidence_base': 0.9,
                'context_boost': 0.1,
                'format_validators': [
                    lambda x: '@' in x,
                    lambda x: '.' in x.split('@')[1] if '@' in x else False,
                    lambda x: len(x.split('@')[1]) > 2 if '@' in x else False
                ]
            },
            
            'phone': {
                'patterns': [
                    re.compile(r'\b(\+?1[-.\s]?(\d{3})[-.\s]?(\d{3})[-.\s]?(\d{4}))\b'),  # US format
                    re.compile(r'\b(\(\d{3}\)\s?-?\s?\d{3}[-.\s]?\d{4})\b'),  # (123) 456-7890
                    re.compile(r'\b(\d{3}[-.\s]?\d{3}[-.\s]?\d{4})\b'),  # 123-456-7890
                    re.compile(r'\b(\+\d{1,3}[-.\s]?\d{1,14})\b'),  # International
                    re.compile(r'\b(\d{10})\b'),  # 10 digits
                ],
                'confidence_base': 0.7,
                'context_boost': 0.2,
                'format_validators': [
                    lambda x: len(re.sub(r'\D', '', x)) >= 10,
                    lambda x: len(re.sub(r'\D', '', x)) <= 15
                ]
            },
            
            'tracking': {
                'patterns': [
                    re.compile(r'\b(1Z[A-Z0-9]{16})\b'),  # UPS tracking
                    re.compile(r'\b(\d{22})\b'),  # FedEx tracking
                    re.compile(r'\b(\d{12})\b'),  # USPS tracking  
                    re.compile(r'\b([A-Z]{2}\d{9}[A-Z]{2})\b'),  # Generic international
                    re.compile(r'\b(TRK\d{10,15})\b', re.IGNORECASE),  # Generic tracking
                ],
                'confidence_base': 0.6,
                'context_boost': 0.3,
                'format_validators': [
                    lambda x: len(x) >= 8,
                    lambda x: any(c.isdigit() for c in x)
                ]
            },
            
            'invoice': {
                'patterns': [
                    re.compile(r'\b(INV-?\d{4,12})\b', re.IGNORECASE),  # INV-123456
                    re.compile(r'\b(\d{6,12})\b'),  # Number sequence
                    re.compile(r'\b([A-Z]{2,4}\d{4,10})\b'),  # Letters + numbers
                ],
                'confidence_base': 0.5,
                'context_boost': 0.4,
                'format_validators': [
                    lambda x: len(x) >= 4,
                    lambda x: any(c.isdigit() for c in x)
                ]
            },
            
            'customer_id': {
                'patterns': [
                    re.compile(r'\b(CUST-?\d{4,12})\b', re.IGNORECASE),  # CUST-123456
                    re.compile(r'\b(C\d{6,12})\b'),  # C123456789
                    re.compile(r'\b(\d{6,15})\b'),  # Long customer numbers
                ],
                'confidence_base': 0.4,
                'context_boost': 0.4,
                'format_validators': [
                    lambda x: len(x) >= 4,
                    lambda x: any(c.isdigit() for c in x)
                ]
            },
            
            'quantity': {
                'patterns': [
                    re.compile(r'\b(\d+)\s*(?:pcs?|pieces?|units?|each|qty|x)\b', re.IGNORECASE),
                    re.compile(r'\bqty:?\s*(\d+)\b', re.IGNORECASE),
                    re.compile(r'\bquantity:?\s*(\d+)\b', re.IGNORECASE),
                ],
                'confidence_base': 0.7,
                'context_boost': 0.2,
                'format_validators': [
                    lambda x: x.isdigit(),
                    lambda x: int(x) > 0 if x.isdigit() else False
                ]
            },
            
            'url': {
                'patterns': [
                    re.compile(r'\b(https?://[^\s<>"{}|\\^`\[\]]+)\b'),
                    re.compile(r'\b(www\.[^\s<>"{}|\\^`\[\]]+\.[a-zA-Z]{2,})\b'),
                ],
                'confidence_base': 0.8,
                'context_boost': 0.1,
                'format_validators': [
                    lambda x: '.' in x,
                    lambda x: len(x) > 5
                ]
            }
        }
    
    def extract_patterns(
        self, 
        text: str, 
        pattern_types: Optional[List[str]] = None,
        context: Optional[str] = None
    ) -> List[ExtractedPattern]:
        """
        Extract structured patterns from text
        
        Args:
            text: Text to search for patterns
            pattern_types: Specific pattern types to extract (None for all)
            context: Additional context to help with extraction
            
        Returns:
            List of extracted patterns with confidence scores
        """
        try:
            extracted_patterns = []
            
            # Determine which patterns to use
            if pattern_types is None:
                pattern_types = list(self.patterns.keys())
            
            for pattern_type in pattern_types:
                if pattern_type not in self.patterns:
                    continue
                
                patterns_found = self._extract_single_pattern_type(
                    text, pattern_type, context
                )
                extracted_patterns.extend(patterns_found)
            
            # Remove duplicates and sort by confidence
            extracted_patterns = self._deduplicate_patterns(extracted_patterns)
            extracted_patterns.sort(key=lambda x: x.confidence, reverse=True)
            
            self.logger.debug(f"Extracted {len(extracted_patterns)} patterns from text")
            return extracted_patterns
            
        except Exception as e:
            self.logger.error(f"Pattern extraction failed: {e}")
            return []
    
    def _extract_single_pattern_type(
        self, 
        text: str, 
        pattern_type: str, 
        context: Optional[str]
    ) -> List[ExtractedPattern]:
        """Extract all instances of a single pattern type"""
        extracted = []
        pattern_config = self.patterns[pattern_type]
        
        for pattern in pattern_config['patterns']:
            matches = pattern.finditer(text)
            
            for match in matches:
                raw_text = match.group(0)
                value = match.group(1) if match.groups() else match.group(0)
                
                # Validate the match
                if not self._validate_pattern_match(value, pattern_config):
                    continue
                
                # Calculate confidence
                confidence = self._calculate_pattern_confidence(
                    value, pattern_type, pattern_config, match.start(), text, context
                )
                
                # Skip low-confidence matches
                if confidence < 0.3:
                    continue
                
                # Extract metadata
                metadata = self._extract_pattern_metadata(
                    value, pattern_type, match, text
                )
                
                extracted_pattern = ExtractedPattern(
                    raw_text=raw_text,
                    pattern_type=pattern_type,
                    confidence=confidence,
                    value=value,
                    context=context,
                    metadata=metadata
                )
                
                extracted.append(extracted_pattern)
        
        return extracted
    
    def _validate_pattern_match(self, value: str, pattern_config: Dict) -> bool:
        """Validate a pattern match using format validators"""
        validators = pattern_config.get('format_validators', [])
        
        for validator in validators:
            try:
                if not validator(value):
                    return False
            except Exception:
                return False
        
        return True
    
    def _calculate_pattern_confidence(
        self, 
        value: str, 
        pattern_type: str, 
        pattern_config: Dict,
        position: int,
        text: str,
        context: Optional[str]
    ) -> float:
        """Calculate confidence score for pattern match"""
        confidence = pattern_config['confidence_base']
        
        # Context boost
        if self._has_pattern_context(pattern_type, position, text, context):
            confidence += pattern_config['context_boost']
        
        # Pattern-specific adjustments
        if pattern_type == 'email':
            # Email validation is very reliable
            if self._validate_email_format(value):
                confidence = min(confidence + 0.1, 1.0)
        
        elif pattern_type == 'phone':
            # Phone number validation
            digit_count = len(re.sub(r'\D', '', value))
            if digit_count == 10:  # US phone
                confidence += 0.1
            elif digit_count == 11 and value.startswith('+1'):  # US with country code
                confidence += 0.1
        
        elif pattern_type in ['order_id', 'sku', 'tracking']:
            # Length and format bonuses
            if len(value) >= 8:
                confidence += 0.05
            if '-' in value or '_' in value:  # Formatted codes
                confidence += 0.05
        
        elif pattern_type == 'quantity':
            # Quantity validation
            try:
                qty = int(value)
                if 1 <= qty <= 10000:  # Reasonable range
                    confidence += 0.1
                elif qty > 10000:
                    confidence -= 0.2  # Suspicious large quantities
            except ValueError:
                confidence -= 0.3
        
        return min(max(confidence, 0.0), 1.0)
    
    def _has_pattern_context(
        self, 
        pattern_type: str, 
        position: int, 
        text: str, 
        context: Optional[str]
    ) -> bool:
        """Check if pattern has supporting context"""
        indicators = self.context_indicators.get(pattern_type, [])
        
        # Check surrounding text
        start = max(0, position - 50)
        end = min(len(text), position + 50)
        surrounding_text = text[start:end].lower()
        
        # Check full context
        full_context = (context or '') + ' ' + surrounding_text
        full_context = full_context.lower()
        
        return any(indicator in full_context for indicator in indicators)
    
    def _validate_email_format(self, email: str) -> bool:
        """Validate email format more thoroughly"""
        if not email or '@' not in email:
            return False
        
        local, domain = email.rsplit('@', 1)
        
        # Basic local part validation
        if not local or len(local) > 64:
            return False
        
        # Basic domain validation
        if not domain or '.' not in domain or len(domain) < 4:
            return False
        
        # Check for valid TLD
        tld = domain.split('.')[-1]
        if len(tld) < 2 or not tld.isalpha():
            return False
        
        return True
    
    def _extract_pattern_metadata(
        self, 
        value: str, 
        pattern_type: str, 
        match, 
        text: str
    ) -> Dict[str, Any]:
        """Extract additional metadata for the pattern"""
        metadata = {}
        
        if pattern_type == 'phone':
            # Extract phone components
            digits = re.sub(r'\D', '', value)
            metadata['digits_only'] = digits
            metadata['formatted'] = self._format_phone_number(digits)
            
            if len(digits) == 10:
                metadata['area_code'] = digits[:3]
                metadata['exchange'] = digits[3:6]
                metadata['number'] = digits[6:]
            
        elif pattern_type == 'email':
            # Extract email components
            if '@' in value:
                local, domain = value.rsplit('@', 1)
                metadata['local'] = local
                metadata['domain'] = domain
                metadata['tld'] = domain.split('.')[-1] if '.' in domain else None
        
        elif pattern_type == 'url':
            # Extract URL components
            if '://' in value:
                protocol, rest = value.split('://', 1)
                metadata['protocol'] = protocol
                if '/' in rest:
                    domain = rest.split('/')[0]
                    path = '/' + '/'.join(rest.split('/')[1:])
                else:
                    domain = rest
                    path = '/'
                metadata['domain'] = domain
                metadata['path'] = path
        
        elif pattern_type == 'quantity':
            # Extract quantity value
            try:
                metadata['numeric_value'] = int(value)
            except ValueError:
                pass
        
        return metadata
    
    def _format_phone_number(self, digits: str) -> str:
        """Format phone number consistently"""
        if len(digits) == 10:
            return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
        elif len(digits) == 11 and digits.startswith('1'):
            return f"+1 ({digits[1:4]}) {digits[4:7]}-{digits[7:]}"
        else:
            return digits
    
    def _deduplicate_patterns(self, patterns: List[ExtractedPattern]) -> List[ExtractedPattern]:
        """Remove duplicate patterns, keeping the highest confidence version"""
        if not patterns:
            return []
        
        # Group by pattern type and normalized value
        pattern_groups = {}
        
        for pattern in patterns:
            # Normalize value for comparison
            normalized_value = self._normalize_value(pattern.value, pattern.pattern_type)
            key = (pattern.pattern_type, normalized_value)
            
            if key not in pattern_groups:
                pattern_groups[key] = []
            pattern_groups[key].append(pattern)
        
        # Keep highest confidence from each group
        unique_patterns = []
        for group in pattern_groups.values():
            best_pattern = max(group, key=lambda x: x.confidence)
            unique_patterns.append(best_pattern)
        
        return unique_patterns
    
    def _normalize_value(self, value: str, pattern_type: str) -> str:
        """Normalize value for deduplication"""
        if pattern_type == 'phone':
            return re.sub(r'\D', '', value)
        elif pattern_type == 'email':
            return value.lower().strip()
        elif pattern_type in ['order_id', 'sku', 'tracking', 'invoice', 'customer_id']:
            return value.upper().strip()
        else:
            return value.strip()
    
    def validate_pattern(self, extracted_pattern: ExtractedPattern) -> Dict[str, Any]:
        """
        Validate an extracted pattern
        
        Args:
            extracted_pattern: Pattern to validate
            
        Returns:
            Validation result with details
        """
        validation_result = {
            'valid': False,
            'score': 0.0,
            'issues': [],
            'suggestions': []
        }
        
        pattern_type = extracted_pattern.pattern_type
        value = extracted_pattern.value
        confidence = extracted_pattern.confidence
        
        score = confidence
        
        # Pattern-specific validation
        if pattern_type == 'email':
            if not self._validate_email_format(value):
                validation_result['issues'].append('Invalid email format')
                score -= 0.3
        
        elif pattern_type == 'phone':
            digits = re.sub(r'\D', '', value)
            if len(digits) < 10:
                validation_result['issues'].append('Phone number too short')
                score -= 0.2
            elif len(digits) > 15:
                validation_result['issues'].append('Phone number too long')
                score -= 0.2
        
        elif pattern_type == 'url':
            if not ('.' in value and len(value) > 5):
                validation_result['issues'].append('Invalid URL format')
                score -= 0.3
        
        elif pattern_type == 'quantity':
            try:
                qty = int(value)
                if qty <= 0:
                    validation_result['issues'].append('Invalid quantity (zero or negative)')
                    score -= 0.5
                elif qty > 10000:
                    validation_result['issues'].append('Unusually large quantity')
                    score -= 0.1
            except ValueError:
                validation_result['issues'].append('Non-numeric quantity')
                score -= 0.5
        
        validation_result['valid'] = score >= 0.5
        validation_result['score'] = max(score, 0.0)
        
        return validation_result
    
    def get_extraction_stats(self, patterns: List[ExtractedPattern]) -> Dict[str, Any]:
        """Get statistics about extracted patterns"""
        if not patterns:
            return {"total_patterns": 0}
        
        confidences = [p.confidence for p in patterns]
        pattern_types = [p.pattern_type for p in patterns]
        
        type_counts = {}
        for pattern_type in pattern_types:
            type_counts[pattern_type] = type_counts.get(pattern_type, 0) + 1
        
        return {
            "total_patterns": len(patterns),
            "avg_confidence": sum(confidences) / len(confidences),
            "max_confidence": max(confidences),
            "min_confidence": min(confidences),
            "high_confidence_patterns": sum(1 for conf in confidences if conf > 0.8),
            "pattern_types_found": list(set(pattern_types)),
            "counts_by_type": type_counts
        }