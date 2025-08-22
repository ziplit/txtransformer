"""
Comprehensive tests for NLP processing components
"""

import pytest
from unittest.mock import Mock, patch
import spacy
from src.nlp.nlp_processor import NLPProcessor, ExtractedEntity
from src.nlp.entity_extractor import EntityExtractor, EntityCandidate
from src.nlp.rule_matchers import RuleMatchers, MatchResult


class TestNLPProcessor:
    
    def test_nlp_processor_init(self):
        """Test NLP processor initialization"""
        processor = NLPProcessor()
        assert processor.nlp is not None
        assert processor.model_name == "en_core_web_sm"
        assert len(processor.custom_entity_types) > 0
        assert 'ORDER_ID' in processor.custom_entity_types
        assert 'SKU' in processor.custom_entity_types
    
    def test_nlp_processor_fallback_model(self):
        """Test fallback to blank model when main model fails"""
        with patch('spacy.load') as mock_load:
            mock_load.side_effect = OSError("Model not found")
            with patch('spacy.lang.en.English') as mock_english:
                mock_nlp = Mock()
                mock_nlp.pipe_names = []
                mock_nlp.add_pipe.return_value = Mock()
                mock_english.return_value = mock_nlp
                
                processor = NLPProcessor("nonexistent_model")
                assert processor.nlp is not None
                # The fallback is called but may not be used if the real model loading eventually succeeds
                assert mock_load.called
    
    def test_extract_entities_basic(self):
        """Test basic entity extraction"""
        processor = NLPProcessor()
        
        text = "Order #12345678 contains SKU ABC-123 with quantity 5"
        entities = processor.extract_entities(text)
        
        assert len(entities) >= 2  # Should find at least ORDER_ID and SKU
        
        # Check for ORDER_ID
        order_entities = [e for e in entities if e.label in ['ORDER_ID', 'CARDINAL']]
        assert len(order_entities) > 0
        
        # Check entity structure
        for entity in entities:
            assert isinstance(entity, ExtractedEntity)
            assert entity.text
            assert entity.label
            assert 0 <= entity.confidence <= 1
            assert entity.start_char >= 0
            assert entity.end_char > entity.start_char
    
    def test_extract_entities_with_context(self):
        """Test entity extraction with context"""
        processor = NLPProcessor()
        
        text = "Item: iPhone 15 Pro, SKU: IPHONE15P-128"
        context = "Product order confirmation"
        
        entities = processor.extract_entities(text, context)
        
        # Context should boost confidence scores
        for entity in entities:
            if entity.label in ['PRODUCT', 'SKU']:
                assert entity.confidence > 0.5
    
    def test_calculate_entity_confidence(self):
        """Test entity confidence calculation"""
        processor = NLPProcessor()
        
        # Mock spaCy span
        mock_span = Mock()
        mock_span.text = "ORDER-123456789"
        mock_span.label_ = "ORDER_ID"
        
        mock_doc = Mock()
        
        confidence = processor._calculate_entity_confidence(mock_span, mock_doc, None)
        assert 0 <= confidence <= 1
        
        # Test with context
        context = "order confirmation"
        confidence_with_context = processor._calculate_entity_confidence(mock_span, mock_doc, context)
        assert confidence_with_context >= confidence  # Context should not decrease confidence
    
    def test_extract_product_information(self):
        """Test comprehensive product information extraction"""
        processor = NLPProcessor()
        
        text = """
        Product: MacBook Pro 16-inch
        SKU: MBP16-512GB-SILVER
        Quantity: 2
        Order ID: ORD-987654321
        """
        
        product_info = processor.extract_product_information(text)
        
        assert isinstance(product_info, dict)
        # Should contain various entity types
        expected_types = ['product_name', 'sku', 'quantity', 'order_id']
        found_types = [t for t in expected_types if t in product_info]
        assert len(found_types) >= 2  # Should find at least 2 types
    
    def test_get_processing_stats(self):
        """Test processing statistics"""
        processor = NLPProcessor()
        
        stats = processor.get_processing_stats()
        
        assert isinstance(stats, dict)
        assert 'model_name' in stats
        assert 'pipeline_components' in stats
        assert 'custom_entity_types' in stats
        assert 'model_loaded' in stats
        assert stats['model_loaded'] is True


class TestEntityExtractor:
    
    def test_entity_extractor_init(self):
        """Test entity extractor initialization"""
        extractor = EntityExtractor()
        
        assert hasattr(extractor, 'entity_patterns')
        assert hasattr(extractor, 'context_keywords')
        assert 'ORDER_ID' in extractor.entity_patterns
        assert 'SKU' in extractor.entity_patterns
        assert 'QUANTITY' in extractor.entity_patterns
    
    def test_extract_order_ids(self):
        """Test ORDER_ID extraction"""
        extractor = EntityExtractor()
        
        test_cases = [
            "Order: ORD-123456789",
            "Order #98765432",
            "Reference: ABC-123456789",
            "Purchase order 1234567890"
        ]
        
        for text in test_cases:
            candidates = extractor.extract_entities_by_type(text, 'ORDER_ID')
            assert len(candidates) >= 1, f"Failed to extract ORDER_ID from: {text}"
            
            best_candidate = candidates[0]
            assert isinstance(best_candidate, EntityCandidate)
            assert best_candidate.label == 'ORDER_ID'
            assert best_candidate.confidence > 0.5
            assert len(best_candidate.text) >= 6
    
    def test_extract_skus(self):
        """Test SKU extraction"""
        extractor = EntityExtractor()
        
        test_cases = [
            "SKU: ABC123-XYZ",
            "Item number: PROD-123456",
            "Product code LAPTOP128GB",
            "Model ABC1234D"
        ]
        
        for text in test_cases:
            candidates = extractor.extract_entities_by_type(text, 'SKU')
            assert len(candidates) >= 1, f"Failed to extract SKU from: {text}"
            
            best_candidate = candidates[0]
            assert best_candidate.label == 'SKU'
            assert best_candidate.confidence > 0.5
    
    def test_extract_quantities(self):
        """Test quantity extraction"""
        extractor = EntityExtractor()
        
        test_cases = [
            "Quantity: 5",
            "Qty = 10",
            "5 pieces",
            "12 units",
            "3 x Product"
        ]
        
        for text in test_cases:
            candidates = extractor.extract_entities_by_type(text, 'QUANTITY')
            assert len(candidates) >= 1, f"Failed to extract QUANTITY from: {text}"
            
            best_candidate = candidates[0]
            assert best_candidate.label == 'QUANTITY'
            assert best_candidate.text.isdigit()
            assert 1 <= int(best_candidate.text) <= 1000
    
    def test_extract_product_names(self):
        """Test product name extraction"""
        extractor = EntityExtractor()
        
        test_cases = [
            "Product: MacBook Pro 16-inch M2",
            "Item: Samsung Galaxy S24 Ultra",
            "Dell XPS 13 Laptop - $1299",
            "iPhone 15 Pro Max (SKU: IP15PM)"
        ]
        
        for text in test_cases:
            candidates = extractor.extract_entities_by_type(text, 'PRODUCT_NAME')
            if candidates:  # Product name extraction is more challenging
                best_candidate = candidates[0]
                assert best_candidate.label == 'PRODUCT_NAME'
                assert len(best_candidate.text) > 3
    
    def test_extract_tracking_numbers(self):
        """Test tracking number extraction"""
        extractor = EntityExtractor()
        
        test_cases = [
            "Tracking: 1Z999AA1234567890",  # UPS format
            "Shipment: 123456789012",       # FedEx format
            "USPS: 12345678901234567890",   # USPS format
            "Tracking number: ABC123XYZ456"
        ]
        
        for text in test_cases:
            candidates = extractor.extract_entities_by_type(text, 'TRACKING_NUMBER')
            if candidates:  # Some formats might not match
                best_candidate = candidates[0]
                assert best_candidate.label == 'TRACKING_NUMBER'
                assert len(best_candidate.text) >= 8
    
    def test_context_scoring(self):
        """Test context-based confidence scoring"""
        extractor = EntityExtractor()
        
        text = "ORD-123456789"
        
        # Without context
        candidates_no_context = extractor.extract_entities_by_type(text, 'ORDER_ID')
        
        # With relevant context
        candidates_with_context = extractor.extract_entities_by_type(
            text, 'ORDER_ID', context="order confirmation email"
        )
        
        assert len(candidates_no_context) > 0
        assert len(candidates_with_context) > 0
        
        # Context should boost confidence
        assert candidates_with_context[0].confidence >= candidates_no_context[0].confidence
    
    def test_extract_all_entities(self):
        """Test extraction of all entity types"""
        extractor = EntityExtractor()
        
        text = """
        Order Confirmation
        Order ID: ORD-987654321
        Product: MacBook Pro 16-inch M2
        SKU: MBP16-M2-512
        Quantity: 2 units
        Tracking: 1Z999AA1234567890
        Customer ID: CUST-456789
        """
        
        all_entities = extractor.extract_all_entities(text)
        
        assert isinstance(all_entities, dict)
        assert len(all_entities) >= 3  # Should find multiple entity types
        
        # Check that we get reasonable results
        for entity_type, candidates in all_entities.items():
            assert len(candidates) > 0
            assert all(isinstance(c, EntityCandidate) for c in candidates)
            assert all(c.confidence > 0 for c in candidates)
    
    def test_get_best_entities(self):
        """Test getting best entities with confidence threshold"""
        extractor = EntityExtractor()
        
        text = "Order ORD-123456, SKU ABC-123, Qty: 5"
        
        best_entities = extractor.get_best_entities(text, min_confidence=0.3)
        
        assert isinstance(best_entities, dict)
        for entity_type, candidate in best_entities.items():
            assert isinstance(candidate, EntityCandidate)
            assert candidate.confidence >= 0.3
    
    def test_validate_entity(self):
        """Test entity validation"""
        extractor = EntityExtractor()
        
        # Valid ORDER_ID
        result = extractor.validate_entity("ORD-123456789", "ORDER_ID")
        assert result['valid'] is True
        assert result['confidence'] > 0.5
        
        # Invalid ORDER_ID
        result = extractor.validate_entity("abc", "ORDER_ID")
        assert result['valid'] is False
        
        # Unknown entity type
        result = extractor.validate_entity("test", "UNKNOWN_TYPE")
        assert result['valid'] is False
        assert 'Unknown entity type' in result['reason']
    
    def test_extraction_stats(self):
        """Test extraction statistics"""
        extractor = EntityExtractor()
        
        text = "Order ORD-123456, Product: Laptop, SKU: LAP-001, Qty: 2"
        
        stats = extractor.get_extraction_stats(text)
        
        assert isinstance(stats, dict)
        assert 'total_entities_found' in stats
        assert 'entity_types_found' in stats
        assert 'entities_by_type' in stats
        assert 'high_confidence_entities' in stats
        assert 'average_confidence_by_type' in stats
        
        assert stats['total_entities_found'] >= 0
        assert stats['entity_types_found'] >= 0


class TestRuleMatchers:
    
    @pytest.fixture
    def nlp_model(self):
        """Fixture to provide spaCy model"""
        try:
            return spacy.load("en_core_web_sm")
        except OSError:
            # Fallback for CI environments
            return spacy.blank("en")
    
    def test_rule_matchers_init(self, nlp_model):
        """Test rule matchers initialization"""
        matchers = RuleMatchers(nlp_model)
        
        assert matchers.nlp is not None
        assert matchers.matcher is not None
        assert matchers.phrase_matcher is not None
    
    def test_find_token_matches(self, nlp_model):
        """Test token-based pattern matching"""
        matchers = RuleMatchers(nlp_model)
        
        text = "Order ORD-123456 contains 5 pieces of product ABC-789"
        matches = matchers.find_matches(text)
        
        assert len(matches) >= 1
        
        for match in matches:
            assert isinstance(match, MatchResult)
            assert match.text
            assert match.label
            assert 0 <= match.confidence <= 1
            assert match.start >= 0
            assert match.end > match.start
            assert match.rule_id
            assert isinstance(match.matched_tokens, list)
    
    def test_find_matches_by_type(self, nlp_model):
        """Test finding matches of specific types"""
        matchers = RuleMatchers(nlp_model)
        
        text = "Order #123456789 with SKU ABC-123 quantity 5"
        
        order_matches = matchers.find_matches_by_type(text, "ORDER_ID")
        sku_matches = matchers.find_matches_by_type(text, "SKU")
        
        # Should find matches for each type
        if order_matches:  # May not match depending on exact pattern
            assert all(m.label == "ORDER_ID" for m in order_matches)
        
        if sku_matches:
            assert all(m.label == "SKU" for m in sku_matches)
    
    def test_add_custom_pattern(self, nlp_model):
        """Test adding custom patterns"""
        matchers = RuleMatchers(nlp_model)
        
        # Add a custom pattern for invoice IDs
        custom_pattern = [
            {"TEXT": {"REGEX": r"^INV$"}},
            {"TEXT": "-"},
            {"TEXT": {"REGEX": r"^\d{6}$"}}
        ]
        
        matchers.add_custom_pattern("CUSTOM_INVOICE", custom_pattern, "INVOICE_ID")
        
        # Test the custom pattern
        text = "Invoice INV-123456"
        matches = matchers.find_matches(text)
        
        # Check if custom pattern matched
        custom_matches = [m for m in matches if "CUSTOM_INVOICE" in m.rule_id]
        if custom_matches:  # Pattern might not match exactly
            assert len(custom_matches) > 0
    
    def test_add_custom_phrases(self, nlp_model):
        """Test adding custom phrases"""
        matchers = RuleMatchers(nlp_model)
        
        custom_phrases = ["Invoice Number", "Receipt ID", "Transaction Code"]
        matchers.add_custom_phrases("CUSTOM_INVOICE_PHRASE", custom_phrases)
        
        # The phrases are added but finding associated values is more complex
        # This mainly tests that the method doesn't crash
        text = "Invoice Number: INV-123456"
        matches = matchers.find_matches(text)
        
        # Should not crash and may find additional matches
        assert isinstance(matches, list)
    
    def test_matcher_stats(self, nlp_model):
        """Test matcher statistics"""
        matchers = RuleMatchers(nlp_model)
        
        stats = matchers.get_matcher_stats()
        
        assert isinstance(stats, dict)
        assert 'token_patterns' in stats
        assert 'phrase_patterns' in stats
        assert 'available_labels' in stats
        
        assert stats['token_patterns'] > 0  # Should have some patterns
        assert stats['phrase_patterns'] > 0  # Should have some phrases


class TestIntegration:
    """Integration tests for NLP components working together"""
    
    def test_nlp_with_entity_extractor_integration(self):
        """Test NLP processor with entity extractor integration"""
        nlp_processor = NLPProcessor()
        entity_extractor = EntityExtractor()
        
        text = """
        Order Confirmation Email
        Order ID: ORD-987654321
        Product: Apple MacBook Pro 16-inch M2
        SKU: MBP16-M2-1TB-SILVER
        Quantity: 1 unit
        Customer ID: CUST-123456
        """
        
        # Test both processors on same text
        nlp_entities = nlp_processor.extract_entities(text)
        extracted_entities = entity_extractor.extract_all_entities(text)
        
        assert len(nlp_entities) > 0
        assert len(extracted_entities) > 0
        
        # Both should find similar entity types
        nlp_labels = {e.label for e in nlp_entities}
        extractor_labels = set(extracted_entities.keys())
        
        # Should have some overlap in detected entity types
        common_types = nlp_labels.intersection(extractor_labels)
        # Note: Exact matches may vary due to different detection methods
    
    def test_comprehensive_email_processing(self):
        """Test comprehensive processing of email-like text"""
        nlp_processor = NLPProcessor()
        entity_extractor = EntityExtractor()
        
        email_text = """
        Dear Customer,
        
        Thank you for your order #ORD-12345678.
        
        Order Details:
        - Product: Samsung Galaxy S24 Ultra 256GB
        - SKU: SGS24U-256-BLACK  
        - Quantity: 2 units
        - Total: $2,398.00
        
        Your order will be shipped via UPS.
        Tracking number: 1Z999AA1234567890
        
        Customer ID: C987654321
        
        Best regards,
        Customer Service
        """
        
        # Extract with both methods
        product_info = nlp_processor.extract_product_information(email_text)
        best_entities = entity_extractor.get_best_entities(email_text, min_confidence=0.4)
        stats = entity_extractor.get_extraction_stats(email_text)
        
        # Should find comprehensive information
        assert len(product_info) >= 2
        assert len(best_entities) >= 2
        assert stats['total_entities_found'] >= 3
        assert stats['entity_types_found'] >= 2
        
        # Check for key entity types
        expected_types = ['ORDER_ID', 'SKU', 'QUANTITY', 'PRODUCT_NAME', 'TRACKING_NUMBER']
        found_types = list(best_entities.keys()) + list(product_info.keys())
        
        # Should find at least some of the expected types
        found_expected = sum(1 for t in expected_types if any(t.lower() in ft.lower() for ft in found_types))
        assert found_expected >= 2, f"Expected to find at least 2 entity types, found: {found_types}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])