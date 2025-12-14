"""
Similarity calculation module.

This module provides the core similarity calculation logic,
combining structured, text, and metadata similarities.
"""

import logging
from typing import Dict, Tuple
import numpy as np

from src.models.deal import Deal
from src.embedding.fusion import MultiModalFusion
from src.utils.config import get_config

logger = logging.getLogger(__name__)


class SimilarityCalculator:
    """
    Calculator for deal similarity scores.
    
    This class orchestrates the similarity calculation process,
    using the fusion strategy to combine different similarity modalities.
    """
    
    def __init__(self, context: str = "default"):
        """
        Initialize similarity calculator.
        
        Args:
            context: Similarity context (default, screening, risk_assessment, etc.)
        """
        self.context = context
        self.fusion = MultiModalFusion(context=context)
    
    def calculate_similarity(self, deal1: Deal, deal2: Deal) -> Tuple[float, Dict[str, float]]:
        """
        Calculate overall similarity between two deals.
        
        Args:
            deal1: First deal
            deal2: Second deal
            
        Returns:
            Tuple of (overall similarity score, detailed breakdown)
        """
        return self.fusion.compute_similarity(deal1, deal2)
    
    def calculate_similarities(self, query_deal: Deal,
                              candidate_deals: list[Deal]) -> list[Tuple[Deal, float, Dict[str, float]]]:
        """
        Calculate similarities between a query deal and multiple candidates.
        
        Args:
            query_deal: Query deal to compare against
            candidate_deals: List of candidate deals
            
        Returns:
            List of (deal, similarity_score, breakdown) tuples
        """
        results = []
        
        for candidate in candidate_deals:
            try:
                score, breakdown = self.calculate_similarity(query_deal, candidate)
                results.append((candidate, score, breakdown))
            except Exception as e:
                logger.error(f"Error calculating similarity: {e}")
                continue
        
        return results
    
    def set_context(self, context: str):
        """
        Change similarity context (adjusts weights).
        
        Args:
            context: New context name
        """
        self.context = context
        self.fusion = MultiModalFusion(context=context)
        logger.info(f"Similarity context changed to: {context}")


