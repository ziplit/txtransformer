"""
Main deterministic processor that orchestrates all deterministic extraction components
"""

import logging
import asyncio
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass, asdict

from .address_extractor import AddressExtractor, ExtractedAddress
from .date_extractor import DateExtractor, ExtractedDate
from .price_extractor import PriceExtractor, ExtractedPrice
from .pattern_extractor import PatternExtractor, ExtractedPattern


@dataclass
class DeterministicResults:
    """Complete results from deterministic extraction"""
    addresses: List[ExtractedAddress]
    dates: List[ExtractedDate]
    prices: List[ExtractedPrice]
    patterns: List[ExtractedPattern]
    metadata: Dict[str, Any]
    confidence: float


class DeterministicProcessor:
    """Main processor for deterministic data extraction"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Initialize all extractors
        self.address_extractor = AddressExtractor()
        self.date_extractor = DateExtractor()
        self.price_extractor = PriceExtractor()
        self.pattern_extractor = PatternExtractor()
        
        self.logger.info("Deterministic processor initialized with all extractors")
    
    async def process_text(
        self, 
        text: str, 
        context: Optional[str] = None,
        extraction_config: Optional[Dict[str, Any]] = None
    ) -> DeterministicResults:
        """
        Process text with all deterministic extractors
        
        Args:
            text: Text to process
            context: Additional context for extraction
            extraction_config: Configuration for specific extractors
            
        Returns:
            Complete extraction results
        """
        try:
            self.logger.info("Starting deterministic extraction", extra={
                "text_length": len(text),
                "has_context": bool(context)
            })
            
            config = extraction_config or {}
            
            # Run all extractors concurrently
            tasks = [
                self._extract_addresses(text, context, config.get('addresses', {})),
                self._extract_dates(text, context, config.get('dates', {})),
                self._extract_prices(text, context, config.get('prices', {})),
                self._extract_patterns(text, context, config.get('patterns', {}))
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Handle any exceptions
            addresses = results[0] if not isinstance(results[0], Exception) else []
            dates = results[1] if not isinstance(results[1], Exception) else []
            prices = results[2] if not isinstance(results[2], Exception) else []
            patterns = results[3] if not isinstance(results[3], Exception) else []
            
            # Log any exceptions
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    extractor_names = ['addresses', 'dates', 'prices', 'patterns']
                    self.logger.error(f"{extractor_names[i]} extraction failed: {result}")
            
            # Calculate overall confidence and metadata
            metadata = self._compile_metadata(addresses, dates, prices, patterns, text)
            overall_confidence = self._calculate_overall_confidence(addresses, dates, prices, patterns)
            
            extraction_results = DeterministicResults(
                addresses=addresses,
                dates=dates,
                prices=prices,
                patterns=patterns,
                metadata=metadata,
                confidence=overall_confidence
            )
            
            self.logger.info("Deterministic extraction completed", extra={
                "addresses_found": len(addresses),
                "dates_found": len(dates),
                "prices_found": len(prices),
                "patterns_found": len(patterns),
                "overall_confidence": overall_confidence
            })
            
            return extraction_results
            
        except Exception as e:
            self.logger.error(f"Deterministic processing failed: {e}")
            
            # Return empty results on failure
            return DeterministicResults(
                addresses=[],
                dates=[],
                prices=[],
                patterns=[],
                metadata={"error": str(e)},
                confidence=0.0
            )
    
    async def _extract_addresses(
        self, 
        text: str, 
        context: Optional[str], 
        config: Dict[str, Any]
    ) -> List[ExtractedAddress]:
        """Extract addresses asynchronously"""
        try:
            loop = asyncio.get_event_loop()
            addresses = await loop.run_in_executor(
                None, 
                self.address_extractor.extract_addresses, 
                text, 
                context
            )
            return addresses
        except Exception as e:
            self.logger.error(f"Address extraction failed: {e}")
            return []
    
    async def _extract_dates(
        self, 
        text: str, 
        context: Optional[str], 
        config: Dict[str, Any]
    ) -> List[ExtractedDate]:
        """Extract dates asynchronously"""
        try:
            loop = asyncio.get_event_loop()
            dates = await loop.run_in_executor(
                None,
                self.date_extractor.extract_dates,
                text,
                context
            )
            return dates
        except Exception as e:
            self.logger.error(f"Date extraction failed: {e}")
            return []
    
    async def _extract_prices(
        self, 
        text: str, 
        context: Optional[str], 
        config: Dict[str, Any]
    ) -> List[ExtractedPrice]:
        """Extract prices asynchronously"""
        try:
            loop = asyncio.get_event_loop()
            prices = await loop.run_in_executor(
                None,
                self.price_extractor.extract_prices,
                text,
                context
            )
            return prices
        except Exception as e:
            self.logger.error(f"Price extraction failed: {e}")
            return []
    
    async def _extract_patterns(
        self, 
        text: str, 
        context: Optional[str], 
        config: Dict[str, Any]
    ) -> List[ExtractedPattern]:
        """Extract patterns asynchronously"""
        try:
            loop = asyncio.get_event_loop()
            pattern_types = config.get('types')  # None means all types
            patterns = await loop.run_in_executor(
                None,
                self.pattern_extractor.extract_patterns,
                text,
                pattern_types,
                context
            )
            return patterns
        except Exception as e:
            self.logger.error(f"Pattern extraction failed: {e}")
            return []
    
    def _compile_metadata(
        self,
        addresses: List[ExtractedAddress],
        dates: List[ExtractedDate],
        prices: List[ExtractedPrice],
        patterns: List[ExtractedPattern],
        original_text: str
    ) -> Dict[str, Any]:
        """Compile metadata from all extractions"""
        metadata = {
            "extraction_stats": {
                "text_length": len(original_text),
                "total_extractions": len(addresses) + len(dates) + len(prices) + len(patterns)
            }
        }
        
        # Add individual extractor stats
        if addresses:
            metadata["address_stats"] = self.address_extractor.get_extraction_stats(addresses)
        
        if dates:
            metadata["date_stats"] = self.date_extractor.get_extraction_stats(dates)
        
        if prices:
            metadata["price_stats"] = self.price_extractor.get_extraction_stats(prices)
        
        if patterns:
            metadata["pattern_stats"] = self.pattern_extractor.get_extraction_stats(patterns)
        
        # Cross-extractor analysis
        metadata["cross_analysis"] = self._perform_cross_analysis(
            addresses, dates, prices, patterns
        )
        
        return metadata
    
    def _calculate_overall_confidence(
        self,
        addresses: List[ExtractedAddress],
        dates: List[ExtractedDate],
        prices: List[ExtractedPrice],
        patterns: List[ExtractedPattern]
    ) -> float:
        """Calculate overall confidence score for the extraction"""
        all_confidences = []
        
        # Collect all confidence scores
        all_confidences.extend([addr.confidence for addr in addresses])
        all_confidences.extend([date.confidence for date in dates])
        all_confidences.extend([price.confidence for price in prices])
        all_confidences.extend([pattern.confidence for pattern in patterns])
        
        if not all_confidences:
            return 0.0
        
        # Weight by number of extractions
        weighted_confidence = sum(all_confidences) / len(all_confidences)
        
        # Bonus for having multiple types of data
        extraction_types = 0
        if addresses: extraction_types += 1
        if dates: extraction_types += 1
        if prices: extraction_types += 1
        if patterns: extraction_types += 1
        
        diversity_bonus = min(extraction_types * 0.05, 0.15)
        
        return min(weighted_confidence + diversity_bonus, 1.0)
    
    def _perform_cross_analysis(
        self,
        addresses: List[ExtractedAddress],
        dates: List[ExtractedDate],
        prices: List[ExtractedPrice],
        patterns: List[ExtractedPattern]
    ) -> Dict[str, Any]:
        """Perform cross-extractor analysis to find relationships"""
        analysis = {}
        
        # Check for order-related patterns
        order_patterns = [p for p in patterns if p.pattern_type == 'order_id']
        order_dates = [d for d in dates if d.date_type == 'order']
        
        if order_patterns and order_dates:
            analysis["potential_orders"] = {
                "order_ids": [p.value for p in order_patterns],
                "order_dates": [d.normalized_date if hasattr(d, 'normalized_date') else str(d.parsed_date.date()) for d in order_dates],
                "confidence": min(
                    sum(p.confidence for p in order_patterns) / len(order_patterns),
                    sum(d.confidence for d in order_dates) / len(order_dates)
                )
            }
        
        # Check for shipping information
        shipping_addresses = [a for a in addresses if 'ship' in (a.context or '').lower()]
        ship_dates = [d for d in dates if d.date_type == 'ship']
        tracking_patterns = [p for p in patterns if p.pattern_type == 'tracking']
        
        if any([shipping_addresses, ship_dates, tracking_patterns]):
            analysis["shipping_info"] = {
                "has_shipping_address": bool(shipping_addresses),
                "has_ship_date": bool(ship_dates),
                "has_tracking": bool(tracking_patterns),
                "tracking_numbers": [p.value for p in tracking_patterns]
            }
        
        # Check for financial summary
        if prices:
            total_prices = [p for p in prices if p.price_type == 'total']
            tax_prices = [p for p in prices if p.price_type == 'tax']
            
            analysis["financial_summary"] = {
                "total_amounts": [{"amount": str(p.amount), "currency": p.currency} for p in total_prices],
                "tax_amounts": [{"amount": str(p.amount), "currency": p.currency} for p in tax_prices],
                "price_count": len(prices),
                "currencies": list(set(p.currency for p in prices))
            }
        
        # Document type inference
        analysis["document_type"] = self._infer_document_type(
            addresses, dates, prices, patterns
        )
        
        return analysis
    
    def _infer_document_type(
        self,
        addresses: List[ExtractedAddress],
        dates: List[ExtractedDate],
        prices: List[ExtractedPrice],
        patterns: List[ExtractedPattern]
    ) -> Dict[str, Any]:
        """Infer the type of document based on extracted data"""
        scores = {
            "order": 0.0,
            "invoice": 0.0,
            "shipping": 0.0,
            "receipt": 0.0,
            "booking": 0.0,
            "unknown": 0.0
        }
        
        # Order indicators
        order_ids = [p for p in patterns if p.pattern_type == 'order_id']
        order_dates = [d for d in dates if d.date_type == 'order']
        if order_ids: scores["order"] += 0.4
        if order_dates: scores["order"] += 0.3
        if prices: scores["order"] += 0.2
        
        # Invoice indicators
        invoice_patterns = [p for p in patterns if p.pattern_type == 'invoice']
        invoice_dates = [d for d in dates if d.date_type == 'invoice']
        if invoice_patterns: scores["invoice"] += 0.4
        if invoice_dates: scores["invoice"] += 0.3
        if prices and any(p.price_type == 'total' for p in prices): scores["invoice"] += 0.3
        
        # Shipping indicators
        tracking = [p for p in patterns if p.pattern_type == 'tracking']
        ship_dates = [d for d in dates if d.date_type == 'ship']
        shipping_addresses = [a for a in addresses if 'ship' in (a.context or '').lower()]
        if tracking: scores["shipping"] += 0.4
        if ship_dates: scores["shipping"] += 0.3
        if shipping_addresses: scores["shipping"] += 0.3
        
        # Receipt indicators
        if prices and len(prices) > 2: scores["receipt"] += 0.3
        if any(p.price_type == 'tax' for p in prices): scores["receipt"] += 0.2
        
        # Determine most likely type
        max_score = max(scores.values())
        if max_score < 0.3:
            most_likely = "unknown"
            confidence = 0.0
        else:
            most_likely = max(scores, key=scores.get)
            confidence = max_score
        
        return {
            "most_likely": most_likely,
            "confidence": confidence,
            "scores": scores
        }
    
    def validate_results(self, results: DeterministicResults) -> Dict[str, Any]:
        """
        Validate the complete extraction results
        
        Args:
            results: Results to validate
            
        Returns:
            Validation summary
        """
        validation_summary = {
            "overall_valid": True,
            "overall_score": 0.0,
            "component_validations": {},
            "issues": [],
            "suggestions": []
        }
        
        total_score = 0.0
        component_count = 0
        
        # Validate addresses
        if results.addresses:
            addr_validations = []
            for addr in results.addresses:
                validation = self.address_extractor.validate_address(addr)
                addr_validations.append(validation)
            
            addr_avg_score = sum(v['score'] for v in addr_validations) / len(addr_validations)
            validation_summary["component_validations"]["addresses"] = {
                "average_score": addr_avg_score,
                "valid_count": sum(1 for v in addr_validations if v['valid']),
                "total_count": len(addr_validations)
            }
            total_score += addr_avg_score
            component_count += 1
        
        # Validate dates
        if results.dates:
            date_validations = []
            for date in results.dates:
                validation = self.date_extractor.validate_date(date)
                date_validations.append(validation)
            
            date_avg_score = sum(v['score'] for v in date_validations) / len(date_validations)
            validation_summary["component_validations"]["dates"] = {
                "average_score": date_avg_score,
                "valid_count": sum(1 for v in date_validations if v['valid']),
                "total_count": len(date_validations)
            }
            total_score += date_avg_score
            component_count += 1
        
        # Validate prices
        if results.prices:
            price_validations = []
            for price in results.prices:
                validation = self.price_extractor.validate_price(price)
                price_validations.append(validation)
            
            price_avg_score = sum(v['score'] for v in price_validations) / len(price_validations)
            validation_summary["component_validations"]["prices"] = {
                "average_score": price_avg_score,
                "valid_count": sum(1 for v in price_validations if v['valid']),
                "total_count": len(price_validations)
            }
            total_score += price_avg_score
            component_count += 1
        
        # Validate patterns
        if results.patterns:
            pattern_validations = []
            for pattern in results.patterns:
                validation = self.pattern_extractor.validate_pattern(pattern)
                pattern_validations.append(validation)
            
            pattern_avg_score = sum(v['score'] for v in pattern_validations) / len(pattern_validations)
            validation_summary["component_validations"]["patterns"] = {
                "average_score": pattern_avg_score,
                "valid_count": sum(1 for v in pattern_validations if v['valid']),
                "total_count": len(pattern_validations)
            }
            total_score += pattern_avg_score
            component_count += 1
        
        # Calculate overall score
        if component_count > 0:
            validation_summary["overall_score"] = total_score / component_count
            validation_summary["overall_valid"] = validation_summary["overall_score"] >= 0.6
        
        return validation_summary
    
    def to_dict(self, results: DeterministicResults) -> Dict[str, Any]:
        """Convert results to dictionary format"""
        return {
            "addresses": [asdict(addr) for addr in results.addresses],
            "dates": [
                {
                    **asdict(date),
                    "parsed_date": date.parsed_date.isoformat()
                }
                for date in results.dates
            ],
            "prices": [
                {
                    **asdict(price),
                    "amount": str(price.amount)
                }
                for price in results.prices
            ],
            "patterns": [asdict(pattern) for pattern in results.patterns],
            "metadata": results.metadata,
            "confidence": results.confidence
        }