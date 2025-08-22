"""
Address extraction using libpostal for standardized address parsing
"""

import logging
import re
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass


@dataclass
class ExtractedAddress:
    """Structured address representation"""
    raw_text: str
    confidence: float
    components: Dict[str, str]
    normalized: str
    context: Optional[str] = None
    coordinates: Optional[Dict[str, float]] = None


class AddressExtractor:
    """Address extraction and parsing using libpostal"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.postal_available = False
        
        # Try to import postal
        try:
            import postal.parser
            import postal.expand
            self.postal_parser = postal.parser
            self.postal_expand = postal.expand
            self.postal_available = True
            self.logger.info("libpostal available for address parsing")
        except ImportError:
            self.logger.warning("libpostal not available, using fallback regex patterns")
            self.postal_parser = None
            self.postal_expand = None
        
        # Fallback regex patterns for common address components
        self.address_patterns = {
            'street_number': re.compile(r'\b\d+\b'),
            'street_name': re.compile(r'\b\d+\s+([A-Za-z\s]+(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Lane|Ln|Boulevard|Blvd|Circle|Cir|Court|Ct|Place|Pl))\b', re.IGNORECASE),
            'city': re.compile(r'\b([A-Za-z\s]{2,}),\s*[A-Z]{2}\s+\d{5}', re.IGNORECASE),
            'state': re.compile(r'\b([A-Z]{2})\s+\d{5}'),
            'postal_code': re.compile(r'\b(\d{5}(?:-\d{4})?)\b'),
            'country': re.compile(r'\b(USA|United States|US|Canada|CA)\b', re.IGNORECASE)
        }
        
        # Common address indicator words
        self.address_indicators = [
            'address', 'street', 'avenue', 'road', 'drive', 'lane', 'boulevard',
            'ship to', 'shipping', 'billing', 'delivery', 'location', 'apt', 'suite'
        ]
    
    def extract_addresses(self, text: str, context: Optional[str] = None) -> List[ExtractedAddress]:
        """
        Extract addresses from text
        
        Args:
            text: Text to search for addresses
            context: Additional context to help with extraction
            
        Returns:
            List of extracted addresses with confidence scores
        """
        try:
            addresses = []
            
            if self.postal_available:
                addresses = self._extract_with_postal(text)
            else:
                addresses = self._extract_with_regex(text, context)
            
            # Add context-based confidence adjustment
            if context:
                addresses = self._adjust_confidence_with_context(addresses, context)
            
            # Sort by confidence
            addresses.sort(key=lambda x: x.confidence, reverse=True)
            
            self.logger.debug(f"Extracted {len(addresses)} addresses from text")
            return addresses
            
        except Exception as e:
            self.logger.error(f"Address extraction failed: {e}")
            return []
    
    def _extract_with_postal(self, text: str) -> List[ExtractedAddress]:
        """Extract addresses using libpostal"""
        addresses = []
        
        try:
            # Split text into potential address lines
            lines = text.split('\n')
            
            for line in lines:
                line = line.strip()
                if len(line) < 10:  # Skip very short lines
                    continue
                
                # Check if line contains address-like patterns
                if not self._looks_like_address(line):
                    continue
                
                # Parse with libpostal
                try:
                    parsed = self.postal_parser.parse_address(line)
                    
                    if parsed and len(parsed) > 2:  # Must have at least a few components
                        components = {comp[1]: comp[0] for comp in parsed}
                        
                        # Generate normalized address
                        normalized = self._normalize_address_components(components)
                        
                        # Calculate confidence based on completeness
                        confidence = self._calculate_postal_confidence(components, line)
                        
                        address = ExtractedAddress(
                            raw_text=line,
                            confidence=confidence,
                            components=components,
                            normalized=normalized,
                            context=context
                        )
                        
                        addresses.append(address)
                        
                except Exception as e:
                    self.logger.debug(f"Failed to parse line with postal: {e}")
                    continue
            
        except Exception as e:
            self.logger.error(f"Postal extraction failed: {e}")
        
        return addresses
    
    def _extract_with_regex(self, text: str, context: Optional[str] = None) -> List[ExtractedAddress]:
        """Extract addresses using regex fallback"""
        addresses = []
        
        try:
            # Look for patterns that might be addresses
            lines = text.split('\n')
            
            for line in lines:
                line = line.strip()
                
                if not self._looks_like_address(line):
                    continue
                
                components = {}
                confidence = 0.0
                
                # Extract components using regex
                for component_name, pattern in self.address_patterns.items():
                    match = pattern.search(line)
                    if match:
                        if component_name == 'street_name':
                            components[component_name] = match.group(1).strip()
                        else:
                            components[component_name] = match.group(1 if match.lastindex else 0).strip()
                        confidence += 0.15
                
                # Must have at least street and postal code or city/state
                has_street = any(comp in components for comp in ['street_name', 'street_number'])
                has_location = any(comp in components for comp in ['postal_code', 'city', 'state'])
                
                if has_street and has_location and confidence > 0.3:
                    normalized = self._normalize_address_components(components)
                    
                    address = ExtractedAddress(
                        raw_text=line,
                        confidence=min(confidence, 0.85),  # Cap regex confidence
                        components=components,
                        normalized=normalized,
                        context=context
                    )
                    
                    addresses.append(address)
            
        except Exception as e:
            self.logger.error(f"Regex address extraction failed: {e}")
        
        return addresses
    
    def _looks_like_address(self, line: str) -> bool:
        """Check if a line looks like it could contain an address"""
        line_lower = line.lower()
        
        # Must have some digits (for street number or postal code)
        if not re.search(r'\d', line):
            return False
        
        # Check for address indicators
        has_indicator = any(indicator in line_lower for indicator in self.address_indicators)
        
        # Check for street suffixes
        street_suffixes = ['street', 'st', 'avenue', 'ave', 'road', 'rd', 'drive', 'dr', 'lane', 'ln']
        has_street_suffix = any(suffix in line_lower for suffix in street_suffixes)
        
        # Check for postal code pattern
        has_postal = bool(self.address_patterns['postal_code'].search(line))
        
        # Check for state abbreviation
        has_state = bool(self.address_patterns['state'].search(line))
        
        return has_indicator or has_street_suffix or has_postal or has_state
    
    def _calculate_postal_confidence(self, components: Dict[str, str], raw_text: str) -> float:
        """Calculate confidence score for postal-parsed address"""
        confidence = 0.0
        
        # Base confidence for using postal
        confidence += 0.4
        
        # Bonus for each component type
        component_bonuses = {
            'house_number': 0.1,
            'road': 0.15,
            'city': 0.1,
            'state': 0.1,
            'postcode': 0.15,
            'country': 0.05
        }
        
        for comp_type in components:
            if comp_type in component_bonuses:
                confidence += component_bonuses[comp_type]
        
        # Length bonus (longer addresses are often more complete)
        if len(raw_text) > 30:
            confidence += 0.05
        
        return min(confidence, 1.0)
    
    def _normalize_address_components(self, components: Dict[str, str]) -> str:
        """Create normalized address string from components"""
        # Standard order for address components
        ordered_parts = []
        
        # Street address
        if 'house_number' in components or 'street_number' in components:
            number = components.get('house_number', components.get('street_number', ''))
            ordered_parts.append(number)
        
        if 'road' in components or 'street_name' in components:
            street = components.get('road', components.get('street_name', ''))
            ordered_parts.append(street)
        
        # City, State ZIP
        city_state_zip = []
        if 'city' in components:
            city_state_zip.append(components['city'])
        
        if 'state' in components:
            city_state_zip.append(components['state'])
        
        if 'postcode' in components or 'postal_code' in components:
            postal = components.get('postcode', components.get('postal_code', ''))
            city_state_zip.append(postal)
        
        if city_state_zip:
            ordered_parts.append(', '.join(city_state_zip))
        
        # Country
        if 'country' in components:
            ordered_parts.append(components['country'])
        
        return ', '.join(part for part in ordered_parts if part.strip())
    
    def _adjust_confidence_with_context(self, addresses: List[ExtractedAddress], context: str) -> List[ExtractedAddress]:
        """Adjust confidence scores based on context"""
        context_lower = context.lower()
        
        # Context indicators that suggest addresses are important
        address_contexts = ['shipping', 'billing', 'delivery', 'send to', 'ship to', 'address']
        
        context_boost = 0.0
        for indicator in address_contexts:
            if indicator in context_lower:
                context_boost = 0.1
                break
        
        # Apply boost to all addresses
        for address in addresses:
            address.confidence = min(address.confidence + context_boost, 1.0)
        
        return addresses
    
    def validate_address(self, address: ExtractedAddress) -> Dict[str, Any]:
        """
        Validate an extracted address
        
        Args:
            address: Address to validate
            
        Returns:
            Validation result with details
        """
        validation_result = {
            'valid': False,
            'score': 0.0,
            'issues': [],
            'suggestions': []
        }
        
        components = address.components
        
        # Check for required components
        has_street = any(comp in components for comp in ['road', 'street_name'])
        has_city = 'city' in components
        has_postal = any(comp in components for comp in ['postcode', 'postal_code'])
        
        score = 0.0
        
        if has_street:
            score += 0.4
        else:
            validation_result['issues'].append('Missing street information')
        
        if has_city:
            score += 0.3
        else:
            validation_result['issues'].append('Missing city')
        
        if has_postal:
            score += 0.3
            # Validate postal code format
            postal = components.get('postcode', components.get('postal_code', ''))
            if not re.match(r'^\d{5}(-\d{4})?$', postal):
                validation_result['issues'].append('Invalid postal code format')
                score -= 0.1
        else:
            validation_result['issues'].append('Missing postal code')
        
        validation_result['valid'] = score >= 0.6
        validation_result['score'] = score
        
        return validation_result
    
    def get_extraction_stats(self, addresses: List[ExtractedAddress]) -> Dict[str, Any]:
        """Get statistics about extracted addresses"""
        if not addresses:
            return {"total_addresses": 0}
        
        confidences = [addr.confidence for addr in addresses]
        
        return {
            "total_addresses": len(addresses),
            "avg_confidence": sum(confidences) / len(confidences),
            "max_confidence": max(confidences),
            "min_confidence": min(confidences),
            "high_confidence_addresses": sum(1 for conf in confidences if conf > 0.8),
            "extraction_method": "libpostal" if self.postal_available else "regex_fallback"
        }