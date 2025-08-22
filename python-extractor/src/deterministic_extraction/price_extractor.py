"""
Price and monetary value extraction using price-parser
"""

import logging
import re
from typing import Dict, List, Any, Optional
from decimal import Decimal, InvalidOperation
from dataclasses import dataclass


@dataclass
class ExtractedPrice:
    """Structured price representation"""
    raw_text: str
    amount: Decimal
    currency: str
    confidence: float
    context: Optional[str] = None
    price_type: Optional[str] = None  # unit_price, total, tax, discount, etc.


class PriceExtractor:
    """Price and monetary value extraction using price-parser"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.price_parser_available = False
        self.babel_available = False
        
        # Try to import price-parser
        try:
            from price_parser import Price
            self.Price = Price
            self.price_parser_available = True
            self.logger.info("price-parser available for monetary value parsing")
        except ImportError:
            self.logger.warning("price-parser not available, using fallback regex patterns")
            self.Price = None
        
        # Try to import Babel for comprehensive currency support
        try:
            from babel.numbers import get_currency_name, get_currency_symbol
            from babel.core import Locale, get_global
            self.get_currency_name = get_currency_name
            self.get_currency_symbol = get_currency_symbol
            self.babel_locale = Locale('en')
            self.babel_available = True
            self.logger.info("Babel available for comprehensive currency support")
        except ImportError:
            self.logger.warning("Babel not available, using limited currency support")
            self.get_currency_name = None
            self.get_currency_symbol = None
            self.babel_locale = None
        
        # Initialize currency data
        self.currency_symbols, self.currency_codes = self._initialize_currency_data()
        
        # Enhanced regex patterns for comprehensive price formats
        self.price_patterns = self._initialize_price_patterns()
        
        # Price context indicators
        self.price_contexts = {
            'unit_price': ['price', 'cost', 'rate', 'each', 'per unit', 'unit cost'],
            'total': ['total', 'amount', 'sum', 'grand total', 'subtotal'],
            'tax': ['tax', 'vat', 'gst', 'sales tax', 'duty'],
            'discount': ['discount', 'off', 'reduction', 'savings', 'rebate'],
            'shipping': ['shipping', 'delivery', 'freight', 'postage'],
            'fee': ['fee', 'charge', 'service charge', 'handling']
        }
    
    def _initialize_currency_data(self) -> tuple[Dict[str, str], List[str]]:
        """Initialize comprehensive currency symbols and codes"""
        
        if self.babel_available:
            # Use Babel to get comprehensive currency data
            currency_symbols = {}
            currency_codes = []
            
            # Major world currencies with their symbols
            major_currencies = [
                'USD', 'EUR', 'GBP', 'JPY', 'CHF', 'CAD', 'AUD', 'NZD',  # Major developed
                'CNY', 'INR', 'KRW', 'SGD', 'HKD', 'TWD', 'THB', 'MYR',  # Asia-Pacific
                'BRL', 'MXN', 'ARS', 'CLP', 'COP', 'PEN',                # Latin America
                'ZAR', 'NGN', 'EGP', 'MAD',                              # Africa
                'RUB', 'PLN', 'CZK', 'HUF', 'RON', 'BGN',               # Eastern Europe
                'TRY', 'ILS', 'AED', 'SAR', 'QAR', 'KWD',               # Middle East
                'SEK', 'NOK', 'DKK', 'ISK',                             # Nordic
            ]
            
            for currency_code in major_currencies:
                try:
                    symbol = self.get_currency_symbol(currency_code, locale=self.babel_locale)
                    if symbol and symbol != currency_code:  # Only if we get a real symbol
                        currency_symbols[symbol] = currency_code
                    currency_codes.append(currency_code)
                except Exception:
                    # Skip currencies that cause issues
                    continue
            
            # Add manual mappings for multi-character symbols that Babel might miss
            additional_symbols = {
                'CA$': 'CAD', 'A$': 'AUD', 'NZ$': 'NZD', 'CN¥': 'CNY',
                'HK$': 'HKD', 'NT$': 'TWD', 'R$': 'BRL', 'MX$': 'MXN'
            }
            currency_symbols.update(additional_symbols)
            
            self.logger.info(f"Loaded {len(currency_codes)} currencies with {len(currency_symbols)} symbols via Babel")
            
        else:
            # Fallback to manual list
            currency_symbols = {
                '$': 'USD', '€': 'EUR', '£': 'GBP', '¥': 'JPY', '₹': 'INR',
                '₽': 'RUB', '₩': 'KRW', '¢': 'USD', '₪': 'ILS', '₫': 'VND',
                '₦': 'NGN', '₨': 'PKR', '₱': 'PHP', '₡': 'CRC', '₲': 'PYG',
                '₴': 'UAH', '₵': 'GHS', '₶': 'LVL', '₷': 'LTL', '₸': 'KZT',
                '₹': 'INR', '₺': 'TRY', '₻': 'MNT', '₼': 'AZN', '₽': 'RUB',
                '₾': 'GEL', '₿': 'BTC', '﷼': 'SAR', '¤': 'GENERIC',
                # Multi-character symbols
                'CA$': 'CAD', 'A$': 'AUD', 'NZ$': 'NZD', 'CN¥': 'CNY',
                'HK$': 'HKD', 'NT$': 'TWD', 'R$': 'BRL', 'MX$': 'MXN'
            }
            
            currency_codes = [
                'USD', 'EUR', 'GBP', 'JPY', 'CHF', 'CAD', 'AUD', 'NZD',
                'CNY', 'INR', 'KRW', 'SGD', 'HKD', 'TWD', 'THB', 'MYR',
                'BRL', 'MXN', 'RUB', 'ZAR', 'SEK', 'NOK', 'DKK', 'PLN',
                'TRY', 'ILS', 'AED', 'SAR', 'EGP', 'NGN', 'PKR', 'VND'
            ]
        
        return currency_symbols, currency_codes
    
    def _initialize_price_patterns(self) -> Dict[str, re.Pattern]:
        """Initialize comprehensive price regex patterns"""
        
        # Separate single-character and multi-character currency symbols
        single_char_symbols = [s for s in self.currency_symbols.keys() if len(s) == 1]
        multi_char_symbols = [s for s in self.currency_symbols.keys() if len(s) > 1]
        
        # Create regex patterns
        single_char_pattern = ''.join(re.escape(symbol) for symbol in single_char_symbols)
        multi_char_pattern = '|'.join(re.escape(symbol) for symbol in multi_char_symbols)
        
        # Combined currency symbol pattern
        if multi_char_symbols:
            currency_symbol_pattern = f'({multi_char_pattern}|[{single_char_pattern}])'
        else:
            currency_symbol_pattern = f'([{single_char_pattern}])'
        
        patterns = {
            # Currency symbol patterns (dynamic based on available symbols)
            'currency_symbol_amount': re.compile(
                rf'{currency_symbol_pattern}\s*(\d{{1,3}}(?:,\d{{3}})*(?:\.\d{{1,4}})?)',
                re.IGNORECASE
            ),
            
            # Amount followed by currency symbol
            'amount_currency_symbol': re.compile(
                rf'(\d{{1,3}}(?:,\d{{3}})*(?:\.\d{{1,4}})?)\s*{currency_symbol_pattern}',
                re.IGNORECASE
            ),
            
            # Amount with currency code
            'amount_currency_code': re.compile(
                r'(\d{1,3}(?:,\d{3})*(?:\.\d{1,4})?)\s*([A-Z]{3})\b',
                re.IGNORECASE
            ),
            
            # Currency code followed by amount
            'currency_code_amount': re.compile(
                r'\b([A-Z]{3})\s*(\d{1,3}(?:,\d{3})*(?:\.\d{1,4})?)',
                re.IGNORECASE
            ),
            
            # Written currency names
            'written_currency': re.compile(
                r'(\d{1,3}(?:,\d{3})*(?:\.\d{1,4})?)\s*(dollars?|euros?|pounds?|yen|yuan|rupees?|rubles?|won|pesos?)\b',
                re.IGNORECASE
            ),
            
            # Generic decimal amounts (in likely price contexts)
            'contextual_decimal': re.compile(
                r'\b(\d{1,3}(?:,\d{3})*\.\d{2})\b'
            ),
            
            # Percentage (for discounts/tax)
            'percentage': re.compile(
                r'(\d+(?:\.\d+)?)\s*%'
            ),
            
            # Scientific notation prices (rare but possible)
            'scientific_notation': re.compile(
                r'(\d+(?:\.\d+)?)[eE]([+-]?\d+)'
            )
        }
        
        return patterns
    
    def extract_prices(self, text: str, context: Optional[str] = None) -> List[ExtractedPrice]:
        """
        Extract monetary values from text
        
        Args:
            text: Text to search for prices
            context: Additional context to help with extraction
            
        Returns:
            List of extracted prices with confidence scores
        """
        try:
            prices = []
            
            if self.price_parser_available:
                prices = self._extract_with_price_parser(text, context)
            else:
                prices = self._extract_with_regex(text, context)
            
            # Remove duplicates and sort by confidence
            prices = self._deduplicate_prices(prices)
            prices.sort(key=lambda x: x.confidence, reverse=True)
            
            self.logger.debug(f"Extracted {len(prices)} prices from text")
            return prices
            
        except Exception as e:
            self.logger.error(f"Price extraction failed: {e}")
            return []
    
    def _extract_with_price_parser(self, text: str, context: Optional[str]) -> List[ExtractedPrice]:
        """Extract prices using price-parser library"""
        prices = []
        
        try:
            # Split text into lines and process each
            lines = text.split('\n')
            processed_text = []
            
            for line in lines:
                line = line.strip()
                if line:
                    processed_text.append(line)
            
            # Also process the full text
            processed_text.append(text)
            
            for text_chunk in processed_text:
                # Find potential price strings
                potential_prices = self._find_potential_price_strings(text_chunk)
                
                for price_text, position in potential_prices:
                    try:
                        # Parse with price-parser
                        parsed_price = self.Price.fromstring(price_text)
                        
                        if parsed_price.amount and parsed_price.amount > 0:
                            confidence = self._calculate_parser_confidence(
                                price_text, parsed_price, context
                            )
                            
                            # Determine price type from context
                            price_type = self._determine_price_type(position, text_chunk, context)
                            
                            # Convert currency symbol to currency code
                            raw_currency = parsed_price.currency or 'USD'
                            currency = self.currency_symbols.get(raw_currency, raw_currency)
                            
                            extracted_price = ExtractedPrice(
                                raw_text=price_text,
                                amount=Decimal(str(parsed_price.amount)),
                                currency=currency,
                                confidence=confidence,
                                context=context,
                                price_type=price_type
                            )
                            
                            prices.append(extracted_price)
                            
                    except Exception as e:
                        self.logger.debug(f"Failed to parse price '{price_text}': {e}")
                        continue
            
        except Exception as e:
            self.logger.error(f"Price parser extraction failed: {e}")
        
        return prices
    
    def _extract_with_regex(self, text: str, context: Optional[str]) -> List[ExtractedPrice]:
        """Extract prices using enhanced regex patterns"""
        prices = []
        
        try:
            for pattern_name, pattern in self.price_patterns.items():
                matches = pattern.finditer(text)
                
                for match in matches:
                    try:
                        # Extract amount and currency based on pattern type
                        amount_str, currency = self._parse_match_groups(pattern_name, match, text)
                        
                        if not amount_str:
                            continue
                        
                        # Clean and convert amount
                        cleaned_amount = amount_str.replace(',', '').replace(' ', '')
                        amount = Decimal(cleaned_amount)
                        
                        if amount <= 0:
                            continue
                        
                        # Skip amounts that are too small unless they're in a price context
                        if amount < Decimal('0.01') and not self._has_price_context(context):
                            continue
                        
                        confidence = self._calculate_regex_confidence(
                            match.group(0), amount, currency, pattern_name, context
                        )
                        
                        price_type = self._determine_price_type(match.start(), text, context)
                        
                        extracted_price = ExtractedPrice(
                            raw_text=match.group(0),
                            amount=amount,
                            currency=currency,
                            confidence=confidence,
                            context=context,
                            price_type=price_type
                        )
                        
                        prices.append(extracted_price)
                        
                    except (InvalidOperation, ValueError) as e:
                        self.logger.debug(f"Failed to parse amount from {match.group(0)}: {e}")
                        continue
            
        except Exception as e:
            self.logger.error(f"Regex price extraction failed: {e}")
        
        return prices
    
    def _parse_match_groups(self, pattern_name: str, match, text: str) -> tuple[str, str]:
        """Parse regex match groups to extract amount and currency"""
        
        if pattern_name == 'currency_symbol_amount':
            # Pattern: €123.45
            symbol = match.group(1)
            amount = match.group(2)
            currency = self.currency_symbols.get(symbol, 'USD')
            return amount, currency
        
        elif pattern_name == 'amount_currency_symbol':
            # Pattern: 123.45€
            amount = match.group(1)
            symbol = match.group(2)
            currency = self.currency_symbols.get(symbol, 'USD')
            return amount, currency
        
        elif pattern_name == 'amount_currency_code':
            # Pattern: 123.45 EUR
            amount = match.group(1)
            currency = match.group(2).upper()
            return amount, currency
        
        elif pattern_name == 'currency_code_amount':
            # Pattern: EUR 123.45
            currency = match.group(1).upper()
            amount = match.group(2)
            return amount, currency
        
        elif pattern_name == 'written_currency':
            # Pattern: 123.45 dollars
            amount = match.group(1)
            currency_word = match.group(2).lower()
            currency_map = {
                'dollars': 'USD', 'dollar': 'USD',
                'euros': 'EUR', 'euro': 'EUR',
                'pounds': 'GBP', 'pound': 'GBP',
                'yen': 'JPY', 'yuan': 'CNY',
                'rupees': 'INR', 'rupee': 'INR',
                'rubles': 'RUB', 'ruble': 'RUB',
                'won': 'KRW', 'pesos': 'MXN', 'peso': 'MXN'
            }
            currency = currency_map.get(currency_word, 'USD')
            return amount, currency
        
        elif pattern_name == 'contextual_decimal':
            # Pattern: 123.45 (context-dependent)
            amount = match.group(1)
            currency = self._infer_currency_from_context(text, match.start())
            return amount, currency
        
        elif pattern_name == 'percentage':
            # Pattern: 15% (treat as percentage, not price)
            amount = match.group(1)
            return amount, 'PCT'  # Special currency code for percentages
        
        elif pattern_name == 'scientific_notation':
            # Pattern: 1.5e3 (rare but possible)
            base = float(match.group(1))
            exp = int(match.group(2))
            amount = str(base * (10 ** exp))
            currency = self._infer_currency_from_context(text, match.start())
            return amount, currency
        
        else:
            # Fallback - try to extract first numeric group
            if match.groups():
                amount = match.group(1)
                currency = self._infer_currency_from_context(text, match.start())
                return amount, currency
        
        return '', 'USD'
    
    def _infer_currency_from_context(self, text: str, position: int) -> str:
        """Infer currency from surrounding text context"""
        # Look at surrounding text
        start = max(0, position - 100)
        end = min(len(text), position + 100)
        surrounding = text[start:end].upper()
        
        # Check for currency codes in surrounding text
        for code in self.currency_codes:
            if code in surrounding:
                return code
        
        # Check for currency symbols
        for symbol, code in self.currency_symbols.items():
            if symbol in surrounding:
                return code
        
        # Check for country/region indicators
        region_indicators = {
            'US': 'USD', 'USA': 'USD', 'UNITED STATES': 'USD',
            'EU': 'EUR', 'EUROPE': 'EUR', 'EUROPEAN': 'EUR',
            'UK': 'GBP', 'BRITAIN': 'GBP', 'BRITISH': 'GBP',
            'JAPAN': 'JPY', 'JAPANESE': 'JPY',
            'CHINA': 'CNY', 'CHINESE': 'CNY',
            'INDIA': 'INR', 'INDIAN': 'INR',
            'CANADA': 'CAD', 'CANADIAN': 'CAD',
            'AUSTRALIA': 'AUD', 'AUSTRALIAN': 'AUD'
        }
        
        for indicator, currency in region_indicators.items():
            if indicator in surrounding:
                return currency
        
        # Default to USD
        return 'USD'
    
    def _find_potential_price_strings(self, text: str) -> List[tuple]:
        """Find potential price strings in text"""
        potential_prices = []
        
        # Look for currency symbols followed by numbers (use dynamic symbols)
        single_char_symbols = [s for s in self.currency_symbols.keys() if len(s) == 1]
        multi_char_symbols = [s for s in self.currency_symbols.keys() if len(s) > 1]
        
        # Multi-character symbols first (longer matches take priority)
        if multi_char_symbols:
            multi_pattern = re.compile(
                rf"({'|'.join(re.escape(s) for s in multi_char_symbols)})\s*\d+[,\d]*\.?\d*", 
                re.IGNORECASE
            )
            matches = multi_pattern.finditer(text)
            for match in matches:
                potential_prices.append((match.group(0), match.start()))
        
        # Single-character symbols
        single_pattern = re.compile(
            rf"[{''.join(re.escape(s) for s in single_char_symbols)}]\s*\d+[,\d]*\.?\d*", 
            re.IGNORECASE
        )
        matches = single_pattern.finditer(text)
        for match in matches:
            # Only add if not already covered by multi-character pattern
            start_pos = match.start()
            if not any(abs(start_pos - pos) < 5 for _, pos in potential_prices):
                potential_prices.append((match.group(0), match.start()))
        
        # Look for numbers followed by currency codes
        code_pattern = re.compile(r'\d+[,\d]*\.?\d*\s*(?:USD|EUR|GBP|JPY|CAD|AUD|CHF|INR|CNY)', re.IGNORECASE)
        matches = code_pattern.finditer(text)
        
        for match in matches:
            potential_prices.append((match.group(0), match.start()))
        
        # Look for currency codes followed by numbers
        code_first_pattern = re.compile(r'(?:USD|EUR|GBP|JPY|CAD|AUD|CHF|INR|CNY)\s+\d+[,\d]*\.?\d*', re.IGNORECASE)
        matches = code_first_pattern.finditer(text)
        
        for match in matches:
            potential_prices.append((match.group(0), match.start()))
        
        # Look for decimal amounts in likely price contexts
        context_words = ['price', 'cost', 'total', 'amount', '$', 'pay', 'charge']
        for word in context_words:
            if word in text.lower():
                decimal_pattern = re.compile(rf'{re.escape(word)}\s*:?\s*(\d+[,\d]*\.\d{{2}})', re.IGNORECASE)
                matches = decimal_pattern.finditer(text)
                
                for match in matches:
                    potential_prices.append((match.group(1), match.start()))
        
        return potential_prices
    
    
    def _calculate_parser_confidence(
        self, 
        price_text: str, 
        parsed_price, 
        context: Optional[str]
    ) -> float:
        """Calculate confidence for price-parser results"""
        confidence = 0.6  # Base confidence for using parser
        
        # Currency symbol bonus
        if parsed_price.currency:
            confidence += 0.2
        
        # Amount reasonableness
        amount = parsed_price.amount
        if 0.01 <= amount <= 1000000:  # Reasonable range
            confidence += 0.1
        elif amount > 1000000:
            confidence -= 0.1  # Very large amounts are suspicious
        
        # Format bonus
        if re.search(r'\d+\.\d{2}$', price_text):  # Proper decimal places
            confidence += 0.1
        
        # Context bonus
        if context and self._has_price_context(context):
            confidence += 0.1
        
        return min(confidence, 1.0)
    
    def _calculate_regex_confidence(
        self, 
        price_text: str, 
        amount: Decimal, 
        currency: str, 
        pattern_name: str, 
        context: Optional[str]
    ) -> float:
        """Calculate confidence for regex-parsed prices"""
        confidence = 0.4  # Lower base confidence for regex
        
        # Pattern-specific bonuses
        pattern_bonuses = {
            'dollar_amount': 0.3,
            'euro_amount': 0.3,
            'pound_amount': 0.3,
            'decimal_with_currency': 0.25,
            'amount_dollar': 0.2,
            'generic_decimal': 0.1
        }
        
        confidence += pattern_bonuses.get(pattern_name, 0.05)
        
        # Price text quality bonus
        if len(price_text) > 3 and not price_text.isdigit():  # More complex price text
            confidence += 0.05
        
        # Currency confidence boost for major currencies
        major_currencies = {'USD', 'EUR', 'GBP', 'JPY', 'CAD', 'AUD'}
        if currency in major_currencies:
            confidence += 0.05
        
        # Amount reasonableness
        if 0.01 <= amount <= 1000000:
            confidence += 0.1
        elif amount > 1000000:
            confidence -= 0.2
        
        # Decimal places bonus
        if '.' in str(amount) and len(str(amount).split('.')[1]) == 2:
            confidence += 0.1
        
        # Context bonus
        if context and self._has_price_context(context):
            confidence += 0.1
        
        return min(confidence, 0.85)  # Cap regex confidence
    
    def _has_price_context(self, context: str) -> bool:
        """Check if context contains price-related indicators"""
        if not context:
            return False
        
        context_lower = context.lower()
        all_indicators = []
        for indicators in self.price_contexts.values():
            all_indicators.extend(indicators)
        
        return any(indicator in context_lower for indicator in all_indicators)
    
    def _determine_price_type(self, position: int, text: str, context: Optional[str]) -> Optional[str]:
        """Determine the type of price based on surrounding context"""
        # Look at text around the price
        start = max(0, position - 30)
        end = min(len(text), position + 30)
        surrounding_text = text[start:end].lower()
        
        # Check context as well
        full_context = (context or '') + ' ' + surrounding_text
        full_context = full_context.lower()
        
        # Check each price type
        for price_type, indicators in self.price_contexts.items():
            if any(indicator in full_context for indicator in indicators):
                return price_type
        
        return None
    
    def _deduplicate_prices(self, prices: List[ExtractedPrice]) -> List[ExtractedPrice]:
        """Remove duplicate prices, keeping the highest confidence version"""
        if not prices:
            return []
        
        # Group by amount and currency
        price_groups = {}
        for price in prices:
            key = (price.amount, price.currency)
            
            if key not in price_groups:
                price_groups[key] = []
            price_groups[key].append(price)
        
        # Keep highest confidence from each group
        unique_prices = []
        for group in price_groups.values():
            best_price = max(group, key=lambda x: x.confidence)
            unique_prices.append(best_price)
        
        return unique_prices
    
    def normalize_currency(self, extracted_price: ExtractedPrice, target_currency: str = 'USD') -> ExtractedPrice:
        """
        Normalize price to target currency (placeholder for currency conversion)
        
        Args:
            extracted_price: Price to normalize
            target_currency: Target currency code
            
        Returns:
            Price with normalized currency (no actual conversion in this implementation)
        """
        # This is a placeholder - in a real implementation, you'd use
        # a currency conversion API like exchangerate-api.com
        
        if extracted_price.currency == target_currency:
            return extracted_price
        
        # For now, just return the original price with a note
        normalized = ExtractedPrice(
            raw_text=extracted_price.raw_text + f" (converted from {extracted_price.currency})",
            amount=extracted_price.amount,  # No actual conversion
            currency=target_currency,
            confidence=extracted_price.confidence * 0.9,  # Slightly lower confidence
            context=extracted_price.context,
            price_type=extracted_price.price_type
        )
        
        return normalized
    
    def validate_price(self, extracted_price: ExtractedPrice) -> Dict[str, Any]:
        """
        Validate an extracted price
        
        Args:
            extracted_price: Price to validate
            
        Returns:
            Validation result with details
        """
        validation_result = {
            'valid': False,
            'score': 0.0,
            'issues': [],
            'suggestions': []
        }
        
        amount = extracted_price.amount
        currency = extracted_price.currency
        
        score = extracted_price.confidence
        
        # Amount validation
        if amount <= 0:
            validation_result['issues'].append('Invalid amount (zero or negative)')
            score -= 0.5
        elif amount > Decimal('1000000'):
            validation_result['issues'].append('Unusually large amount')
            score -= 0.1
        elif amount < Decimal('0.01'):
            validation_result['issues'].append('Unusually small amount')
            score -= 0.1
        
        # Currency validation
        if currency not in self.currency_codes and currency not in self.currency_symbols.values():
            validation_result['issues'].append('Unrecognized currency code')
            score -= 0.2
        
        # Decimal places check for certain currencies
        if currency in ['USD', 'EUR', 'GBP', 'CAD', 'AUD']:
            decimal_places = len(str(amount).split('.')[1]) if '.' in str(amount) else 0
            if decimal_places > 2:
                validation_result['issues'].append('Too many decimal places for currency')
                score -= 0.1
        
        validation_result['valid'] = score >= 0.5
        validation_result['score'] = max(score, 0.0)
        
        return validation_result
    
    def calculate_totals(self, prices: List[ExtractedPrice], by_type: bool = False) -> Dict[str, Any]:
        """
        Calculate totals from extracted prices
        
        Args:
            prices: List of extracted prices
            by_type: Whether to group by price type
            
        Returns:
            Dictionary with calculated totals
        """
        if not prices:
            return {"total_amount": Decimal('0'), "currency": "USD", "count": 0}
        
        if by_type:
            totals_by_type = {}
            
            for price in prices:
                price_type = price.price_type or 'unknown'
                
                if price_type not in totals_by_type:
                    totals_by_type[price_type] = {
                        'total_amount': Decimal('0'),
                        'currency': price.currency,
                        'count': 0,
                        'prices': []
                    }
                
                # Only add if same currency (simplified approach)
                if totals_by_type[price_type]['currency'] == price.currency:
                    totals_by_type[price_type]['total_amount'] += price.amount
                    totals_by_type[price_type]['count'] += 1
                    totals_by_type[price_type]['prices'].append(price)
            
            return totals_by_type
        
        else:
            # Simple total (assumes same currency)
            primary_currency = prices[0].currency
            total_amount = Decimal('0')
            count = 0
            
            for price in prices:
                if price.currency == primary_currency:
                    total_amount += price.amount
                    count += 1
            
            return {
                "total_amount": total_amount,
                "currency": primary_currency,
                "count": count,
                "prices": prices
            }
    
    def get_extraction_stats(self, prices: List[ExtractedPrice]) -> Dict[str, Any]:
        """Get statistics about extracted prices"""
        if not prices:
            return {"total_prices": 0}
        
        confidences = [price.confidence for price in prices]
        currencies = [price.currency for price in prices]
        price_types = [price.price_type for price in prices if price.price_type]
        amounts = [float(price.amount) for price in prices]
        
        return {
            "total_prices": len(prices),
            "avg_confidence": sum(confidences) / len(confidences),
            "max_confidence": max(confidences),
            "min_confidence": min(confidences),
            "currencies_found": list(set(currencies)),
            "price_types_found": list(set(price_types)),
            "total_value_by_currency": {
                currency: sum(float(p.amount) for p in prices if p.currency == currency)
                for currency in set(currencies)
            },
            "avg_amount": sum(amounts) / len(amounts),
            "extraction_method": "price_parser" if self.price_parser_available else "regex_fallback"
        }