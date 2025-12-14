"""
Tag extractor for qualitative pattern recognition.

This module extracts qualitative tags and risk indicators from deal documents
to support similarity matching beyond structured metrics.

According to the consolidated document, this module:
- Identifies patterns such as "roll-up platform," "software with usage-based pricing,"
  "regulated market," "customer concentration," "contracted revenue"
- Extracts risk indicators and business model characteristics
- Supports qualitative similarity matching
"""

import re
import logging
from typing import List, Dict, Set
from collections import defaultdict

logger = logging.getLogger(__name__)


class TagExtractor:
    """
    Extractor for qualitative tags and patterns from deal documents.
    
    This class identifies:
    - Business model patterns (pricing models, revenue types, go-to-market)
    - Risk indicators (customer concentration, churn risk, regulatory risk)
    - Market characteristics (platform effects, network effects, moats)
    
    Tags are used to enhance similarity matching and provide explainability
    in search results.
    """
    
    # Pattern definitions for tag extraction
    TAG_PATTERNS: Dict[str, Dict[str, List[str]]] = {
        # Business model tags
        "usage_pricing": {
            "keywords": [
                "usage-based", "usage based", "pay per use", "consumption-based",
                "metered", "pay-as-you-go", "per-user pricing", "per-seat"
            ],
            "weight": 1.0
        },
        "subscription_pricing": {
            "keywords": [
                "subscription", "recurring", "sas", "software as a service",
                "monthly subscription", "annual subscription", "mrr", "arr"
            ],
            "weight": 1.0
        },
        "recurring_revenue": {
            "keywords": [
                "recurring revenue", "recurring revenues", "arr", "annual recurring revenue",
                "mrr", "monthly recurring revenue", "contractual revenue", "contracted revenue"
            ],
            "weight": 1.2  # Higher weight as it's a strong signal
        },
        "platform_business": {
            "keywords": [
                "platform", "marketplace", "network effects", "two-sided market",
                "multi-sided platform", "ecosystem"
            ],
            "weight": 1.0
        },
        "roll_up": {
            "keywords": [
                "roll-up", "rollup", "consolidation strategy", "acquisition platform",
                "buy-and-build", "consolidator"
            ],
            "weight": 1.1
        },
        
        # Customer and market characteristics
        "b2b": {
            "keywords": [
                "b2b", "business to business", "enterprise", "b-to-b",
                "business customers", "corporate customers"
            ],
            "weight": 1.0
        },
        "b2c": {
            "keywords": [
                "b2c", "business to consumer", "consumer", "b-to-c",
                "end consumers", "retail customers"
            ],
            "weight": 1.0
        },
        "high_customer_concentration": {
            "keywords": [
                "customer concentration", "top customer", "key customer",
                "customer concentration risk", "revenue concentration",
                "dependency on", "relies heavily on customers"
            ],
            "weight": 1.2  # Important risk indicator
        },
        
        # Risk indicators
        "high_churn_risk": {
            "keywords": [
                "churn", "customer retention", "attrition", "customer loss",
                "retention challenges", "churn rate", "customer turnover"
            ],
            "weight": 1.2
        },
        "regulatory_risk": {
            "keywords": [
                "regulated", "regulation", "regulatory", "compliance",
                "fda", "sec", "hipaa", "gdpr", "regulatory risk",
                "compliance requirements", "regulatory approval"
            ],
            "weight": 1.1
        },
        "key_person_risk": {
            "keywords": [
                "key person", "key personnel", "founder dependency",
                "management depth", "succession risk", "key employee"
            ],
            "weight": 1.0
        },
        
        # Industry/market tags
        "healthcare": {
            "keywords": [
                "healthcare", "health care", "medical", "clinical",
                "health services", "patient", "provider"
            ],
            "weight": 0.8  # Lower weight as it's also captured in sector
        },
        "financial_services": {
            "keywords": [
                "financial services", "fintech", "banking", "payment",
                "lending", "insurance", "wealth management"
            ],
            "weight": 0.8
        },
        "saas": {
            "keywords": [
                "saas", "software as a service", "cloud software",
                "software platform", "web-based software"
            ],
            "weight": 0.9
        },
        
        # Growth and market characteristics
        "high_growth": {
            "keywords": [
                "high growth", "rapid growth", "fast-growing", "growth trajectory",
                "expanding rapidly", "accelerating growth"
            ],
            "weight": 0.8
        },
        "market_leader": {
            "keywords": [
                "market leader", "leading", "dominant position",
                "number one", "#1", "market share leader"
            ],
            "weight": 0.7
        },
        
        # Revenue characteristics
        "contracted_revenue": {
            "keywords": [
                "contracted revenue", "contractual", "long-term contracts",
                "multi-year contracts", "contract backlog"
            ],
            "weight": 1.1
        },
        "project_based": {
            "keywords": [
                "project-based", "project revenue", "one-time projects",
                "custom projects", "professional services"
            ],
            "weight": 0.9
        }
    }
    
    def __init__(self, case_sensitive: bool = False):
        """
        Initialize tag extractor.
        
        Args:
            case_sensitive: Whether keyword matching should be case-sensitive
        """
        self.case_sensitive = case_sensitive
        self._compile_patterns()
    
    def _compile_patterns(self):
        """Compile regex patterns for efficient matching."""
        self.compiled_patterns = {}
        
        for tag_name, tag_config in self.TAG_PATTERNS.items():
            keywords = tag_config["keywords"]
            patterns = []
            
            for keyword in keywords:
                if self.case_sensitive:
                    pattern = re.compile(r'\b' + re.escape(keyword) + r'\b', re.IGNORECASE)
                else:
                    pattern = re.compile(r'\b' + re.escape(keyword) + r'\b', re.IGNORECASE)
                patterns.append(pattern)
            
            self.compiled_patterns[tag_name] = {
                "patterns": patterns,
                "weight": tag_config["weight"]
            }
    
    def extract_tags(self, text: str, min_confidence: float = 0.5) -> List[str]:
        """
        Extract qualitative tags from text.
        
        Args:
            text: Text content to analyze
            min_confidence: Minimum confidence threshold for including a tag
            
        Returns:
            List of tag names that were detected
        """
        if not text or not text.strip():
            return []
        
        # Normalize text for matching
        if not self.case_sensitive:
            text_lower = text.lower()
        else:
            text_lower = text
        
        detected_tags = []
        tag_scores = defaultdict(float)
        
        # Match patterns and calculate confidence scores
        for tag_name, tag_config in self.compiled_patterns.items():
            patterns = tag_config["patterns"]
            weight = tag_config["weight"]
            
            match_count = 0
            for pattern in patterns:
                matches = len(pattern.findall(text_lower))
                match_count += matches
            
            if match_count > 0:
                # Confidence is based on number of matches and tag weight
                confidence = min(1.0, match_count * 0.3 * weight)
                tag_scores[tag_name] = confidence
        
        # Filter by minimum confidence and return tag names
        detected_tags = [
            tag_name for tag_name, score in tag_scores.items()
            if score >= min_confidence
        ]
        
        # Sort by confidence (descending)
        detected_tags.sort(key=lambda t: tag_scores[t], reverse=True)
        
        logger.debug(f"Extracted {len(detected_tags)} tags from text: {detected_tags}")
        
        return detected_tags
    
    def extract_tags_with_scores(self, text: str) -> Dict[str, float]:
        """
        Extract tags with confidence scores.
        
        Args:
            text: Text content to analyze
            
        Returns:
            Dictionary mapping tag names to confidence scores [0.0, 1.0]
        """
        if not text or not text.strip():
            return {}
        
        text_lower = text.lower() if not self.case_sensitive else text
        tag_scores = {}
        
        for tag_name, tag_config in self.compiled_patterns.items():
            patterns = tag_config["patterns"]
            weight = tag_config["weight"]
            
            match_count = 0
            for pattern in patterns:
                matches = len(pattern.findall(text_lower))
                match_count += matches
            
            if match_count > 0:
                confidence = min(1.0, match_count * 0.3 * weight)
                tag_scores[tag_name] = confidence
        
        return tag_scores
    
    def get_tag_categories(self) -> Dict[str, List[str]]:
        """
        Get tags organized by category.
        
        Returns:
            Dictionary mapping category names to lists of tag names
        """
        categories = {
            "business_model": [
                "usage_pricing", "subscription_pricing", "recurring_revenue",
                "platform_business", "roll_up", "contracted_revenue", "project_based"
            ],
            "customer_market": [
                "b2b", "b2c", "high_customer_concentration"
            ],
            "risk_indicators": [
                "high_churn_risk", "regulatory_risk", "key_person_risk"
            ],
            "industry": [
                "healthcare", "financial_services", "saas"
            ],
            "characteristics": [
                "high_growth", "market_leader"
            ]
        }
        
        return categories
    
    def compute_tag_similarity(self, tags1: List[str], tags2: List[str]) -> float:
        """
        Compute similarity between two sets of tags.
        
        Uses Jaccard similarity (intersection over union).
        
        Args:
            tags1: First set of tags
            tags2: Second set of tags
            
        Returns:
            Similarity score between 0.0 and 1.0
        """
        if not tags1 and not tags2:
            return 1.0
        
        if not tags1 or not tags2:
            return 0.0
        
        set1 = set(tags1)
        set2 = set(tags2)
        
        intersection = len(set1 & set2)
        union = len(set1 | set2)
        
        if union == 0:
            return 0.0
        
        similarity = intersection / union
        return similarity

