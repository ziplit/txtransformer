"""
Date extraction using dateparser for flexible date parsing
"""

import logging
import re
from typing import Dict, List, Any, Optional, Union
from datetime import datetime, date
from dataclasses import dataclass


@dataclass
class ExtractedDate:
    """Structured date representation"""
    raw_text: str
    parsed_date: datetime
    confidence: float
    format_detected: str
    context: Optional[str] = None
    date_type: Optional[str] = None  # order_date, ship_date, due_date, etc.


class DateExtractor:
    """Date extraction and parsing using dateparser"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.dateparser_available = False
        
        # Try to import dateparser
        try:
            import dateparser
            self.dateparser = dateparser
            self.dateparser_available = True
            self.logger.info("dateparser available for date parsing")
        except ImportError:
            self.logger.warning("dateparser not available, using fallback datetime parsing")
            self.dateparser = None
        
        # Fallback regex patterns for common date formats
        self.date_patterns = {
            'iso_date': re.compile(r'\b(\d{4}-\d{1,2}-\d{1,2})\b'),
            'us_date': re.compile(r'\b(\d{1,2}/\d{1,2}/\d{2,4})\b'),
            'us_date_dash': re.compile(r'\b(\d{1,2}-\d{1,2}-\d{2,4})\b'),
            'written_date': re.compile(r'\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}\b', re.IGNORECASE),
            'short_written': re.compile(r'\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},?\s+\d{4}\b', re.IGNORECASE),
            'european': re.compile(r'\b(\d{1,2}\.\d{1,2}\.\d{4})\b'),
            'timestamp': re.compile(r'\b(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})\b')
        }
        
        # Date context indicators
        self.date_contexts = {
            'order': ['order date', 'ordered', 'purchased', 'bought'],
            'ship': ['ship date', 'shipped', 'delivery', 'sent'],
            'due': ['due date', 'payment due', 'expires', 'expiry'],
            'invoice': ['invoice date', 'billed', 'billing date'],
            'event': ['event date', 'scheduled', 'appointment'],
            'created': ['created', 'generated', 'issued']
        }
        
        # Dateparser settings for different scenarios
        self.dateparser_settings = {
            'PREFER_DAY_OF_MONTH': 'first',
            'PREFER_DATES_FROM': 'past',
            'RETURN_AS_TIMEZONE_AWARE': False,
            'DATE_ORDER': 'MDY',  # US format by default
            'STRICT_PARSING': False
        }
    
    def extract_dates(self, text: str, context: Optional[str] = None) -> List[ExtractedDate]:
        """
        Extract dates from text
        
        Args:
            text: Text to search for dates
            context: Additional context to help with extraction
            
        Returns:
            List of extracted dates with confidence scores
        """
        try:
            dates = []
            
            if self.dateparser_available:
                dates = self._extract_with_dateparser(text, context)
            else:
                dates = self._extract_with_regex(text, context)
            
            # Remove duplicates and sort by confidence
            dates = self._deduplicate_dates(dates)
            dates.sort(key=lambda x: x.confidence, reverse=True)
            
            self.logger.debug(f"Extracted {len(dates)} dates from text")
            return dates
            
        except Exception as e:
            self.logger.error(f"Date extraction failed: {e}")
            return []
    
    def _extract_with_dateparser(self, text: str, context: Optional[str]) -> List[ExtractedDate]:
        """Extract dates using dateparser library"""
        dates = []
        
        try:
            # First, try to find explicit date patterns
            for pattern_name, pattern in self.date_patterns.items():
                matches = pattern.finditer(text)
                
                for match in matches:
                    date_text = match.group(1)
                    
                    # Parse with dateparser
                    try:
                        parsed_date = self.dateparser.parse(
                            date_text, 
                            settings=self.dateparser_settings
                        )
                        
                        if parsed_date:
                            confidence = self._calculate_dateparser_confidence(
                                date_text, parsed_date, pattern_name, context
                            )
                            
                            # Determine date type from context
                            date_type = self._determine_date_type(match.start(), text, context)
                            
                            extracted_date = ExtractedDate(
                                raw_text=date_text,
                                parsed_date=parsed_date,
                                confidence=confidence,
                                format_detected=pattern_name,
                                context=context,
                                date_type=date_type
                            )
                            
                            dates.append(extracted_date)
                            
                    except Exception as e:
                        self.logger.debug(f"Failed to parse date '{date_text}': {e}")
                        continue
            
            # Also try parsing full lines that might contain dates
            lines = text.split('\n')
            for line in lines:
                line = line.strip()
                if len(line) < 6 or len(line) > 100:  # Skip very short or long lines
                    continue
                
                # Skip if we already found dates from this line
                if any(date.raw_text in line for date in dates):
                    continue
                
                try:
                    parsed_date = self.dateparser.parse(line, settings=self.dateparser_settings)
                    
                    if parsed_date and self._is_reasonable_date(parsed_date):
                        confidence = self._calculate_line_confidence(line, parsed_date, context)
                        
                        if confidence > 0.3:  # Only include if reasonably confident
                            date_type = self._determine_date_type(0, line, context)
                            
                            extracted_date = ExtractedDate(
                                raw_text=line,
                                parsed_date=parsed_date,
                                confidence=confidence,
                                format_detected='full_line',
                                context=context,
                                date_type=date_type
                            )
                            
                            dates.append(extracted_date)
                            
                except Exception:
                    continue
            
        except Exception as e:
            self.logger.error(f"Dateparser extraction failed: {e}")
        
        return dates
    
    def _extract_with_regex(self, text: str, context: Optional[str]) -> List[ExtractedDate]:
        """Extract dates using regex fallback"""
        dates = []
        
        try:
            for pattern_name, pattern in self.date_patterns.items():
                matches = pattern.finditer(text)
                
                for match in matches:
                    date_text = match.group(1)
                    
                    # Try to parse with standard datetime
                    parsed_date = self._parse_with_datetime(date_text, pattern_name)
                    
                    if parsed_date:
                        confidence = self._calculate_regex_confidence(
                            date_text, parsed_date, pattern_name, context
                        )
                        
                        date_type = self._determine_date_type(match.start(), text, context)
                        
                        extracted_date = ExtractedDate(
                            raw_text=date_text,
                            parsed_date=parsed_date,
                            confidence=confidence,
                            format_detected=pattern_name,
                            context=context,
                            date_type=date_type
                        )
                        
                        dates.append(extracted_date)
            
        except Exception as e:
            self.logger.error(f"Regex date extraction failed: {e}")
        
        return dates
    
    def _parse_with_datetime(self, date_text: str, pattern_name: str) -> Optional[datetime]:
        """Parse date using standard datetime formats"""
        formats_by_pattern = {
            'iso_date': ['%Y-%m-%d'],
            'us_date': ['%m/%d/%Y', '%m/%d/%y'],
            'us_date_dash': ['%m-%d-%Y', '%m-%d-%y'],
            'european': ['%d.%m.%Y'],
            'timestamp': ['%Y-%m-%dT%H:%M:%S'],
            'written_date': ['%B %d, %Y', '%B %d %Y'],
            'short_written': ['%b %d, %Y', '%b %d %Y']
        }
        
        formats = formats_by_pattern.get(pattern_name, [])
        
        for fmt in formats:
            try:
                return datetime.strptime(date_text, fmt)
            except ValueError:
                continue
        
        return None
    
    def _calculate_dateparser_confidence(
        self, 
        date_text: str, 
        parsed_date: datetime, 
        pattern_name: str, 
        context: Optional[str]
    ) -> float:
        """Calculate confidence score for dateparser-parsed date"""
        confidence = 0.0
        
        # Base confidence for using dateparser
        confidence += 0.5
        
        # Pattern-specific bonuses
        pattern_bonuses = {
            'iso_date': 0.3,
            'timestamp': 0.3,
            'us_date': 0.2,
            'written_date': 0.25,
            'short_written': 0.2,
            'european': 0.15,
            'full_line': 0.1
        }
        
        confidence += pattern_bonuses.get(pattern_name, 0.1)
        
        # Date reasonableness check
        if self._is_reasonable_date(parsed_date):
            confidence += 0.1
        else:
            confidence -= 0.2
        
        # Context bonus
        if context and self._has_date_context(context):
            confidence += 0.1
        
        return min(confidence, 1.0)
    
    def _calculate_regex_confidence(
        self, 
        date_text: str, 
        parsed_date: datetime, 
        pattern_name: str, 
        context: Optional[str]
    ) -> float:
        """Calculate confidence for regex-parsed date"""
        confidence = 0.3  # Lower base confidence for regex
        
        # Pattern bonuses (slightly lower than dateparser)
        pattern_bonuses = {
            'iso_date': 0.25,
            'timestamp': 0.25,
            'us_date': 0.15,
            'written_date': 0.2,
            'short_written': 0.15,
            'european': 0.1
        }
        
        confidence += pattern_bonuses.get(pattern_name, 0.05)
        
        # Reasonableness check
        if self._is_reasonable_date(parsed_date):
            confidence += 0.1
        else:
            confidence -= 0.3
        
        # Context bonus
        if context and self._has_date_context(context):
            confidence += 0.1
        
        return min(confidence, 0.85)  # Cap regex confidence
    
    def _calculate_line_confidence(
        self, 
        line: str, 
        parsed_date: datetime, 
        context: Optional[str]
    ) -> float:
        """Calculate confidence for full-line date parsing"""
        confidence = 0.2  # Lower base for full lines
        
        # Length penalty for very long lines
        if len(line) > 50:
            confidence -= 0.1
        
        # Bonus for date-like words
        date_words = ['date', 'on', 'due', 'expires', 'scheduled']
        if any(word in line.lower() for word in date_words):
            confidence += 0.2
        
        # Reasonableness check
        if self._is_reasonable_date(parsed_date):
            confidence += 0.1
        
        return max(confidence, 0.0)
    
    def _is_reasonable_date(self, date_obj: datetime) -> bool:
        """Check if date is within reasonable bounds"""
        current_year = datetime.now().year
        date_year = date_obj.year
        
        # Must be within reasonable range (1900 to 10 years in future)
        return 1900 <= date_year <= current_year + 10
    
    def _has_date_context(self, context: str) -> bool:
        """Check if context contains date-related indicators"""
        if not context:
            return False
        
        context_lower = context.lower()
        all_indicators = []
        for indicators in self.date_contexts.values():
            all_indicators.extend(indicators)
        
        return any(indicator in context_lower for indicator in all_indicators)
    
    def _determine_date_type(self, position: int, text: str, context: Optional[str]) -> Optional[str]:
        """Determine the type of date based on surrounding context"""
        # Look at text around the date
        start = max(0, position - 50)
        end = min(len(text), position + 50)
        surrounding_text = text[start:end].lower()
        
        # Check context as well
        full_context = (context or '') + ' ' + surrounding_text
        full_context = full_context.lower()
        
        # Check each date type
        for date_type, indicators in self.date_contexts.items():
            if any(indicator in full_context for indicator in indicators):
                return date_type
        
        return None
    
    def _deduplicate_dates(self, dates: List[ExtractedDate]) -> List[ExtractedDate]:
        """Remove duplicate dates, keeping the highest confidence version"""
        if not dates:
            return []
        
        # Group by parsed date (day)
        date_groups = {}
        for extracted_date in dates:
            day_key = extracted_date.parsed_date.date()
            
            if day_key not in date_groups:
                date_groups[day_key] = []
            date_groups[day_key].append(extracted_date)
        
        # Keep highest confidence from each group
        unique_dates = []
        for group in date_groups.values():
            best_date = max(group, key=lambda x: x.confidence)
            unique_dates.append(best_date)
        
        return unique_dates
    
    def normalize_date(self, extracted_date: ExtractedDate, output_format: str = 'iso') -> str:
        """
        Normalize date to standard format
        
        Args:
            extracted_date: Date to normalize
            output_format: 'iso', 'us', 'european', or custom strftime format
            
        Returns:
            Formatted date string
        """
        date_obj = extracted_date.parsed_date
        
        if output_format == 'iso':
            return date_obj.strftime('%Y-%m-%d')
        elif output_format == 'us':
            return date_obj.strftime('%m/%d/%Y')
        elif output_format == 'european':
            return date_obj.strftime('%d.%m.%Y')
        else:
            # Assume custom format
            try:
                return date_obj.strftime(output_format)
            except ValueError:
                return date_obj.strftime('%Y-%m-%d')  # Fallback to ISO
    
    def validate_date(self, extracted_date: ExtractedDate) -> Dict[str, Any]:
        """
        Validate an extracted date
        
        Args:
            extracted_date: Date to validate
            
        Returns:
            Validation result with details
        """
        validation_result = {
            'valid': False,
            'score': 0.0,
            'issues': [],
            'suggestions': []
        }
        
        date_obj = extracted_date.parsed_date
        current_date = datetime.now()
        
        score = extracted_date.confidence
        
        # Check if date is reasonable
        if not self._is_reasonable_date(date_obj):
            validation_result['issues'].append('Date outside reasonable range')
            score -= 0.3
        
        # Check if future date makes sense for certain types
        if extracted_date.date_type in ['order', 'invoice', 'created'] and date_obj > current_date:
            validation_result['issues'].append('Future date for historical event')
            score -= 0.2
        
        # Check if past date makes sense for certain types  
        if extracted_date.date_type in ['ship', 'due', 'event'] and date_obj < current_date:
            days_past = (current_date - date_obj).days
            if days_past > 365:  # More than a year old
                validation_result['issues'].append('Very old date for future event')
                score -= 0.1
        
        validation_result['valid'] = score >= 0.5
        validation_result['score'] = max(score, 0.0)
        
        return validation_result
    
    def get_extraction_stats(self, dates: List[ExtractedDate]) -> Dict[str, Any]:
        """Get statistics about extracted dates"""
        if not dates:
            return {"total_dates": 0}
        
        confidences = [date.confidence for date in dates]
        date_types = [date.date_type for date in dates if date.date_type]
        
        return {
            "total_dates": len(dates),
            "avg_confidence": sum(confidences) / len(confidences),
            "max_confidence": max(confidences),
            "min_confidence": min(confidences),
            "high_confidence_dates": sum(1 for conf in confidences if conf > 0.8),
            "date_types_found": list(set(date_types)),
            "extraction_method": "dateparser" if self.dateparser_available else "regex_fallback"
        }