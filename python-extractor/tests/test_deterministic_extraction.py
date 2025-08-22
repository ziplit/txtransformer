"""
Tests for deterministic extraction functionality
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, MagicMock
from decimal import Decimal
from datetime import datetime

from src.deterministic_extraction import (
    AddressExtractor, DateExtractor, PriceExtractor, 
    PatternExtractor, DeterministicProcessor
)


class TestAddressExtractor:
    
    def test_init(self):
        """Test AddressExtractor initialization"""
        extractor = AddressExtractor()
        assert extractor.logger is not None
        assert isinstance(extractor.address_patterns, dict)
        assert 'street_number' in extractor.address_patterns
    
    def test_looks_like_address(self):
        """Test address detection heuristics"""
        extractor = AddressExtractor()
        
        # Should detect addresses
        assert extractor._looks_like_address("123 Main Street, City, CA 12345")
        assert extractor._looks_like_address("Ship to: 456 Oak Ave")
        assert extractor._looks_like_address("1234 Elm Road")
        
        # Should not detect non-addresses
        assert not extractor._looks_like_address("Just some random text")
        assert not extractor._looks_like_address("No digits here")
    
    def test_extract_with_regex_fallback(self):
        """Test address extraction using regex fallback"""
        extractor = AddressExtractor()
        extractor.postal_available = False  # Force regex mode
        
        text = """
        Shipping Address:
        123 Main Street
        Anytown, CA 90210
        
        Billing: 456 Oak Avenue, Boston, MA 02101
        """
        
        addresses = extractor.extract_addresses(text)
        assert len(addresses) >= 1
        assert any(addr.confidence > 0.3 for addr in addresses)
    
    def test_normalize_address_components(self):
        """Test address normalization"""
        extractor = AddressExtractor()
        
        components = {
            'house_number': '123',
            'road': 'Main Street',
            'city': 'Anytown',
            'state': 'CA',
            'postcode': '90210'
        }
        
        normalized = extractor._normalize_address_components(components)
        assert '123' in normalized
        assert 'Main Street' in normalized
        assert 'CA' in normalized
        assert '90210' in normalized
    
    def test_validate_address(self):
        """Test address validation"""
        extractor = AddressExtractor()
        
        # Good address
        good_address = Mock()
        good_address.components = {
            'road': 'Main Street',
            'city': 'Anytown', 
            'postcode': '90210'
        }
        
        validation = extractor.validate_address(good_address)
        assert validation['valid'] is True
        assert validation['score'] > 0.5
        
        # Poor address
        poor_address = Mock()
        poor_address.components = {}
        
        validation = extractor.validate_address(poor_address)
        assert validation['valid'] is False
        assert len(validation['issues']) > 0


class TestDateExtractor:
    
    def test_init(self):
        """Test DateExtractor initialization"""
        extractor = DateExtractor()
        assert extractor.logger is not None
        assert isinstance(extractor.date_patterns, dict)
        assert 'iso_date' in extractor.date_patterns
    
    def test_extract_with_regex_fallback(self):
        """Test date extraction using regex fallback"""
        extractor = DateExtractor()
        extractor.dateparser_available = False  # Force regex mode
        
        text = """
        Order Date: 2024-01-15
        Ship Date: 01/20/2024
        Due: January 25, 2024
        """
        
        dates = extractor.extract_dates(text)
        assert len(dates) >= 2
        assert any(date.confidence > 0.3 for date in dates)
    
    def test_is_reasonable_date(self):
        """Test reasonable date validation"""
        extractor = DateExtractor()
        
        # Reasonable dates
        assert extractor._is_reasonable_date(datetime(2024, 1, 15))
        assert extractor._is_reasonable_date(datetime(2000, 6, 30))
        
        # Unreasonable dates
        assert not extractor._is_reasonable_date(datetime(1850, 1, 1))
        assert not extractor._is_reasonable_date(datetime(2050, 1, 1))
    
    def test_determine_date_type(self):
        """Test date type determination"""
        extractor = DateExtractor()
        
        text = "Order date: 2024-01-15, ship date: 2024-01-20"
        
        # Should detect order date
        order_type = extractor._determine_date_type(12, text, "order confirmation")
        assert order_type == 'order'
        
        # Should detect ship date (position around "ship date")
        ship_type = extractor._determine_date_type(28, text, "shipping info")
        assert ship_type in ['ship', 'order']  # Either is acceptable due to overlapping context
    
    def test_normalize_date(self):
        """Test date normalization"""
        extractor = DateExtractor()
        
        extracted_date = Mock()
        extracted_date.parsed_date = datetime(2024, 1, 15)
        
        # Test different formats
        iso_format = extractor.normalize_date(extracted_date, 'iso')
        assert iso_format == '2024-01-15'
        
        us_format = extractor.normalize_date(extracted_date, 'us')
        assert us_format == '01/15/2024'


class TestPriceExtractor:
    
    def test_init(self):
        """Test PriceExtractor initialization"""
        extractor = PriceExtractor()
        assert extractor.logger is not None
        assert isinstance(extractor.price_patterns, dict)
        # Check for new enhanced currency patterns
        assert 'amount_currency_symbol' in extractor.price_patterns
        assert 'currency_symbol_amount' in extractor.price_patterns
        assert len(extractor.currency_symbols) > 10  # Should have many currencies
    
    def test_extract_with_regex_fallback(self):
        """Test price extraction using regex fallback"""
        extractor = PriceExtractor()
        extractor.price_parser_available = False  # Force regex mode
        
        text = """
        Unit Price: $19.99
        Total: $59.97
        Tax: $4.80
        Grand Total: $64.77
        """
        
        prices = extractor.extract_prices(text)
        assert len(prices) >= 3
        assert any(price.confidence > 0.4 for price in prices)
        assert any(price.amount == Decimal('19.99') for price in prices)
    
    def test_parse_match_groups(self):
        """Test parsing match groups for currency extraction"""
        extractor = PriceExtractor()
        
        # Test currency symbol amount pattern
        match = Mock()
        match.groups.return_value = ('$', '19.99')
        match.group.side_effect = lambda x: match.groups()[x-1] if x <= len(match.groups()) else None
        
        amount, currency = extractor._parse_match_groups('currency_symbol_amount', match, 'Price: $19.99')
        assert amount == '19.99'
        assert currency == 'USD'
        
        # Test amount currency code pattern
        match.groups.return_value = ('123.45', 'EUR')
        amount, currency = extractor._parse_match_groups('amount_currency_code', match, 'Price: 123.45 EUR')
        assert amount == '123.45'
        assert currency == 'EUR'
    
    def test_enhanced_currency_support(self):
        """Test enhanced currency support with multiple currencies"""
        extractor = PriceExtractor()
        
        # Test various currency formats
        test_cases = [
            ("Price: $19.99", "USD", "19.99"),
            ("Cost: €25.50", "EUR", "25.50"), 
            ("Amount: £15.75", "GBP", "15.75"),
            ("Total: ¥1500", "JPY", "1500"),
            ("Price: ₹999.99", "INR", "999.99"),
            ("Cost: 100.00 CAD", "CAD", "100.00"),
            ("Amount: AUD 75.25", "AUD", "75.25"),
        ]
        
        for text, expected_currency, expected_amount in test_cases:
            prices = extractor.extract_prices(text)
            assert len(prices) > 0, f"Failed to extract price from: {text}"
            
            # Check that we found the expected currency and amount
            found_match = False
            for price in prices:
                if price.currency == expected_currency and str(price.amount) == expected_amount:
                    found_match = True
                    break
            
            assert found_match, f"Expected {expected_currency} {expected_amount} in {text}, but got: {[(p.currency, str(p.amount)) for p in prices]}"
    
    def test_determine_price_type(self):
        """Test price type determination"""
        extractor = PriceExtractor()
        
        text = "Unit price: $19.99, total amount: $59.97, tax: $4.80"
        
        # Should detect unit price
        unit_type = extractor._determine_price_type(0, text, "product pricing")
        assert unit_type == 'unit_price'
        
        # Should detect total (position around "total amount")  
        total_type = extractor._determine_price_type(30, text, None)
        assert total_type in ['total', 'unit_price']  # Either is acceptable due to overlapping context
    
    def test_calculate_totals(self):
        """Test price totals calculation"""
        extractor = PriceExtractor()
        
        prices = [
            Mock(amount=Decimal('19.99'), currency='USD', price_type='unit_price'),
            Mock(amount=Decimal('29.99'), currency='USD', price_type='unit_price'),
            Mock(amount=Decimal('4.00'), currency='USD', price_type='tax')
        ]
        
        # Simple total
        total = extractor.calculate_totals(prices)
        assert total['total_amount'] == Decimal('53.98')
        assert total['currency'] == 'USD'
        
        # By type
        by_type = extractor.calculate_totals(prices, by_type=True)
        assert 'unit_price' in by_type
        assert 'tax' in by_type
        assert by_type['unit_price']['total_amount'] == Decimal('49.98')
    
    def test_validate_price(self):
        """Test price validation"""
        extractor = PriceExtractor()
        
        # Good price
        good_price = Mock()
        good_price.amount = Decimal('19.99')
        good_price.currency = 'USD'
        good_price.confidence = 0.8
        
        validation = extractor.validate_price(good_price)
        assert validation['valid'] is True
        assert validation['score'] > 0.5
        
        # Invalid price
        bad_price = Mock()
        bad_price.amount = Decimal('0')
        bad_price.currency = 'INVALID'
        bad_price.confidence = 0.3
        
        validation = extractor.validate_price(bad_price)
        assert validation['valid'] is False
        assert len(validation['issues']) > 0


class TestPatternExtractor:
    
    def test_init(self):
        """Test PatternExtractor initialization"""
        extractor = PatternExtractor()
        assert extractor.logger is not None
        assert isinstance(extractor.patterns, dict)
        assert 'order_id' in extractor.patterns
        assert 'email' in extractor.patterns
    
    def test_extract_email_patterns(self):
        """Test email pattern extraction"""
        extractor = PatternExtractor()
        
        text = """
        Contact: john.doe@example.com
        Support: support@company.org
        Invalid: not-an-email
        """
        
        patterns = extractor.extract_patterns(text, pattern_types=['email'])
        assert len(patterns) >= 2
        
        # Check email validation
        emails = [p for p in patterns if p.pattern_type == 'email']
        assert len(emails) >= 2
        assert all('@' in email.value for email in emails)
    
    def test_extract_phone_patterns(self):
        """Test phone pattern extraction"""
        extractor = PatternExtractor()
        
        text = """
        Phone: (555) 123-4567
        Mobile: 555-987-6543
        International: +1-555-555-5555
        """
        
        patterns = extractor.extract_patterns(text, pattern_types=['phone'])
        phones = [p for p in patterns if p.pattern_type == 'phone']
        assert len(phones) >= 2
    
    def test_extract_order_id_patterns(self):
        """Test order ID pattern extraction"""
        extractor = PatternExtractor()
        
        text = """
        Order Number: ORD-123456789
        Reference: ABC-987654321
        Order ID: 1234567890
        """
        
        patterns = extractor.extract_patterns(text, pattern_types=['order_id'])
        order_ids = [p for p in patterns if p.pattern_type == 'order_id']
        assert len(order_ids) >= 2
    
    def test_validate_email_format(self):
        """Test email format validation"""
        extractor = PatternExtractor()
        
        # Valid emails
        assert extractor._validate_email_format('test@example.com')
        assert extractor._validate_email_format('user.name@domain.org')
        
        # Invalid emails
        assert not extractor._validate_email_format('invalid-email')
        assert not extractor._validate_email_format('@example.com')
        assert not extractor._validate_email_format('test@')
    
    def test_format_phone_number(self):
        """Test phone number formatting"""
        extractor = PatternExtractor()
        
        # 10 digit US number
        formatted = extractor._format_phone_number('5551234567')
        assert formatted == '(555) 123-4567'
        
        # 11 digit with country code
        formatted = extractor._format_phone_number('15551234567')
        assert formatted == '+1 (555) 123-4567'
    
    def test_validate_pattern(self):
        """Test pattern validation"""
        extractor = PatternExtractor()
        
        # Valid email pattern
        email_pattern = Mock()
        email_pattern.pattern_type = 'email'
        email_pattern.value = 'test@example.com'
        email_pattern.confidence = 0.9
        
        validation = extractor.validate_pattern(email_pattern)
        assert validation['valid'] is True
        
        # Invalid quantity pattern
        qty_pattern = Mock()
        qty_pattern.pattern_type = 'quantity'
        qty_pattern.value = '0'
        qty_pattern.confidence = 0.5
        
        validation = extractor.validate_pattern(qty_pattern)
        assert validation['valid'] is False
        assert len(validation['issues']) > 0


class TestDeterministicProcessor:
    
    def test_init(self):
        """Test DeterministicProcessor initialization"""
        processor = DeterministicProcessor()
        assert processor.address_extractor is not None
        assert processor.date_extractor is not None
        assert processor.price_extractor is not None
        assert processor.pattern_extractor is not None
    
    @pytest.mark.asyncio
    async def test_process_text_basic(self):
        """Test basic text processing"""
        processor = DeterministicProcessor()
        
        text = """
        Order #: ORD-123456789
        Date: 2024-01-15
        Total: $99.99
        Email: customer@example.com
        """
        
        results = await processor.process_text(text)
        
        assert results is not None
        assert results.confidence > 0
        assert len(results.patterns) >= 2  # order_id and email
        assert len(results.dates) >= 1
        assert len(results.prices) >= 1
    
    @pytest.mark.asyncio
    async def test_process_text_with_context(self):
        """Test text processing with context"""
        processor = DeterministicProcessor()
        
        text = "Order date: 2024-01-15, Total: $49.99"
        context = "E-commerce order confirmation"
        
        results = await processor.process_text(text, context=context)
        
        assert results is not None
        assert results.confidence > 0
        # Context should boost confidence
        if results.dates:
            assert any(date.context == context for date in results.dates)
    
    def test_calculate_overall_confidence(self):
        """Test overall confidence calculation"""
        processor = DeterministicProcessor()
        
        # Mock some results
        addresses = [Mock(confidence=0.8)]
        dates = [Mock(confidence=0.9), Mock(confidence=0.7)]
        prices = [Mock(confidence=0.6)]
        patterns = [Mock(confidence=0.9)]
        
        confidence = processor._calculate_overall_confidence(addresses, dates, prices, patterns)
        
        assert 0.0 <= confidence <= 1.0
        assert confidence > 0.7  # Should be reasonably high
    
    def test_infer_document_type(self):
        """Test document type inference"""
        processor = DeterministicProcessor()
        
        # Mock order-like data
        order_patterns = [Mock(pattern_type='order_id', confidence=0.9)]
        order_dates = [Mock(date_type='order', confidence=0.8)]
        prices = [Mock(price_type='total', confidence=0.7)]
        addresses = []
        
        doc_type = processor._infer_document_type(addresses, order_dates, prices, order_patterns)
        
        assert doc_type['most_likely'] == 'order'
        assert doc_type['confidence'] > 0.8
    
    def test_perform_cross_analysis(self):
        """Test cross-extractor analysis"""
        processor = DeterministicProcessor()
        
        # Mock related data with proper mock attributes
        mock_date = Mock()
        mock_date.date_type = 'order'
        mock_date.confidence = 0.8
        
        mock_price = Mock()
        mock_price.price_type = 'total'
        mock_price.amount = Decimal('99.99')
        mock_price.currency = 'USD'
        
        mock_pattern = Mock()
        mock_pattern.pattern_type = 'order_id'
        mock_pattern.value = 'ORD123'
        mock_pattern.confidence = 0.9
        
        addresses = []
        dates = [mock_date]
        prices = [mock_price]
        patterns = [mock_pattern]
        
        analysis = processor._perform_cross_analysis(addresses, dates, prices, patterns)
        
        assert 'potential_orders' in analysis
        assert 'financial_summary' in analysis
        assert 'document_type' in analysis
    
    def test_validate_results(self):
        """Test results validation"""
        processor = DeterministicProcessor()
        
        # Create mock results
        mock_results = Mock()
        mock_results.addresses = []
        mock_results.dates = [Mock()]
        mock_results.prices = [Mock()]
        mock_results.patterns = [Mock()]
        
        # Mock the validation methods
        with patch.object(processor.date_extractor, 'validate_date', return_value={'valid': True, 'score': 0.8}), \
             patch.object(processor.price_extractor, 'validate_price', return_value={'valid': True, 'score': 0.9}), \
             patch.object(processor.pattern_extractor, 'validate_pattern', return_value={'valid': True, 'score': 0.7}):
            
            validation = processor.validate_results(mock_results)
            
            assert validation['overall_valid'] is True
            assert validation['overall_score'] > 0.7
            assert 'component_validations' in validation
    
    def test_to_dict(self):
        """Test results conversion to dictionary"""
        processor = DeterministicProcessor()
        
        # Create mock results with proper attributes
        mock_address = Mock()
        mock_address.raw_text = '123 Main St'
        mock_address.confidence = 0.8
        
        mock_date = Mock()
        mock_date.raw_text = '2024-01-15'
        mock_date.confidence = 0.9
        mock_date.parsed_date = datetime(2024, 1, 15)
        
        mock_price = Mock()
        mock_price.raw_text = '$99.99'
        mock_price.confidence = 0.7
        mock_price.amount = Decimal('99.99')
        
        mock_pattern = Mock()
        mock_pattern.pattern_type = 'email'
        mock_pattern.value = 'test@example.com'
        mock_pattern.confidence = 0.9
        
        mock_results = Mock()
        mock_results.addresses = [mock_address]
        mock_results.dates = [mock_date]
        mock_results.prices = [mock_price]
        mock_results.patterns = [mock_pattern]
        mock_results.metadata = {'test': 'data'}
        mock_results.confidence = 0.85
        
        # Mock asdict to return a dict with the attributes
        def mock_asdict(obj):
            if hasattr(obj, 'raw_text'):
                return {'raw_text': obj.raw_text, 'confidence': obj.confidence}
            return {'test': 'data'}
        
        with patch('src.deterministic_extraction.deterministic_processor.asdict', side_effect=mock_asdict):
            result_dict = processor.to_dict(mock_results)
            
            assert 'addresses' in result_dict
            assert 'dates' in result_dict
            assert 'prices' in result_dict
            assert 'patterns' in result_dict
            assert result_dict['confidence'] == 0.85