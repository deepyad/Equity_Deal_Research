"""
Result ranking module.

This module handles ranking and filtering of similarity search results,
including diversity penalties, recency boosts, feedback-based boosts, and
personalization features.

According to the consolidated document, this module implements:
- Ranking & Re-ranking with diversity penalty, recency boost, feedback boost, personalization
- Fallback handling for low-confidence matches
- Result formatting with attribution breakdown
"""

import logging
from typing import List, Tuple, Dict, Optional, Set
from datetime import datetime
from src.models.deal import Deal
from src.utils.config import get_config

logger = logging.getLogger(__name__)


class ResultRanker:
    """
    Ranks and filters similarity search results.
    
    This class handles:
    - Sorting by similarity score with threshold filtering (Decision Point D3)
    - Diversity penalty to avoid duplicate/similar results
    - Recency boost for more recent deals
    - Feedback-based boost using analyst feedback history
    - Personalization based on analyst preferences
    - Fallback handling for low-confidence matches
    
    According to the consolidated document:
    - Decision Point D3: Match quality threshold check (>0.6)
    - If below threshold: trigger fallback handler
    - If above threshold: proceed with ranking and re-ranking
    """
    
    def __init__(self, enable_recency_boost: bool = True, enable_feedback_boost: bool = True):
        """
        Initialize result ranker.
        
        Args:
            enable_recency_boost: Whether to apply recency boost
            enable_feedback_boost: Whether to apply feedback-based boost
        """
        config = get_config()
        retrieval_config = config.get_retrieval_config()
        self.similarity_threshold = retrieval_config.get("similarity_threshold", 0.6)
        self.max_results = retrieval_config.get("max_results", 20)
        self.enable_recency_boost = enable_recency_boost
        self.enable_feedback_boost = enable_feedback_boost
        
        # Feedback logger for boost calculation (lazy import)
        self._feedback_logger = None
    
    def rank_results(self, results: List[Tuple[Deal, float, Dict[str, float]]],
                    apply_threshold: bool = True,
                    max_results: Optional[int] = None) -> List[Tuple[Deal, float, Dict[str, float]]]:
        """
        Rank and filter similarity results.
        
        Args:
            results: List of (deal, score, breakdown) tuples
            apply_threshold: Whether to filter by similarity threshold
            max_results: Maximum number of results (overrides config)
            
        Returns:
            Sorted and filtered list of results
        """
        if max_results is None:
            max_results = self.max_results
        
        # Sort by similarity score (descending)
        sorted_results = sorted(results, key=lambda x: x[1], reverse=True)
        
        # Apply threshold filter
        if apply_threshold:
            filtered_results = [
                r for r in sorted_results
                if r[1] >= self.similarity_threshold
            ]
        else:
            filtered_results = sorted_results
        
        # Apply max results limit
        final_results = filtered_results[:max_results]
        
        logger.debug(
            f"Ranked {len(results)} results: "
            f"{len(filtered_results)} passed threshold, "
            f"{len(final_results)} returned"
        )
        
        return final_results
    
    def rank_results(
        self,
        results: List[Tuple[Deal, float, Dict[str, float]]],
        apply_threshold: bool = True,
        max_results: Optional[int] = None,
        current_year: Optional[int] = None,
        analyst_id: Optional[str] = None
    ) -> List[Tuple[Deal, float, Dict[str, float]]]:
        """
        Rank and filter similarity results with enhancements.
        
        Applies comprehensive ranking including:
        1. Similarity threshold filtering (Decision Point D3)
        2. Diversity penalty
        3. Recency boost
        4. Feedback boost (if enabled)
        5. Personalization (if analyst_id provided)
        
        Args:
            results: List of (deal, score, breakdown) tuples
            apply_threshold: Whether to filter by similarity threshold
            max_results: Maximum number of results (overrides config)
            current_year: Current year for recency calculation (defaults to current)
            analyst_id: Optional analyst ID for personalization
            
        Returns:
            Sorted and filtered list of results
        """
        if max_results is None:
            max_results = self.max_results
        
        if not results:
            return []
        
        # Decision Point D3: Check match quality threshold
        if apply_threshold:
            filtered_results = [
                r for r in results
                if r[1] >= self.similarity_threshold
            ]
            
            if not filtered_results:
                logger.warning(
                    f"No results above threshold {self.similarity_threshold}, "
                    "should trigger fallback handler"
                )
                # Still return some results for fallback handling
                filtered_results = sorted(results, key=lambda x: x[1], reverse=True)[:5]
        else:
            filtered_results = results
        
        # Apply ranking enhancements
        enhanced_results = self._apply_ranking_enhancements(
            filtered_results,
            current_year=current_year,
            analyst_id=analyst_id
        )
        
        # Apply max results limit
        final_results = enhanced_results[:max_results]
        
        logger.debug(
            f"Ranked {len(results)} results: "
            f"{len(filtered_results)} passed threshold, "
            f"{len(final_results)} returned"
        )
        
        return final_results
    
    def _apply_ranking_enhancements(
        self,
        results: List[Tuple[Deal, float, Dict[str, float]]],
        current_year: Optional[int] = None,
        analyst_id: Optional[str] = None
    ) -> List[Tuple[Deal, float, Dict[str, float]]]:
        """
        Apply all ranking enhancements to results.
        
        Args:
            results: List of (deal, score, breakdown) tuples
            current_year: Current year for recency calculation
            analyst_id: Optional analyst ID for personalization
            
        Returns:
            Enhanced and re-ranked results
        """
        if current_year is None:
            current_year = datetime.now().year
        
        enhanced_results = []
        
        for deal, score, breakdown in results:
            adjusted_score = score
            
            # 1. Diversity penalty
            adjusted_score = self._apply_diversity_penalty(
                deal, adjusted_score, enhanced_results
            )
            
            # 2. Recency boost
            if self.enable_recency_boost:
                recency_boost = self._calculate_recency_boost(
                    deal.metadata.deal_year, current_year
                )
                adjusted_score += recency_boost * 0.1  # 10% max boost
            
            # 3. Feedback boost
            if self.enable_feedback_boost:
                feedback_boost = self._calculate_feedback_boost(deal.metadata.deal_id)
                adjusted_score += feedback_boost * 0.15  # 15% max boost
            
            # 4. Personalization
            if analyst_id:
                personalization_boost = self._calculate_personalization_boost(
                    deal, analyst_id
                )
                adjusted_score += personalization_boost * 0.1  # 10% max boost
            
            # Clamp score to [0, 1]
            adjusted_score = max(0.0, min(1.0, adjusted_score))
            
            enhanced_results.append((deal, adjusted_score, breakdown))
        
        # Re-sort by adjusted score
        enhanced_results.sort(key=lambda x: x[1], reverse=True)
        
        return enhanced_results
    
    def _apply_diversity_penalty(
        self,
        deal: Deal,
        score: float,
        existing_results: List[Tuple[Deal, float, Dict[str, float]]],
        penalty_factor: float = 0.1
    ) -> float:
        """
        Apply diversity penalty to reduce duplicate results.
        
        Penalizes deals that are too similar to higher-ranked deals.
        
        Args:
            deal: Current deal
            score: Current similarity score
            existing_results: Already ranked results
            penalty_factor: Strength of diversity penalty (0-1)
            
        Returns:
            Adjusted score
        """
        if penalty_factor == 0 or not existing_results:
            return score
        
        metadata = deal.metadata
        seen_sectors: Set[str] = set()
        seen_geographies: Set[str] = set()
        seen_companies: Set[str] = set()
        
        for existing_deal, _, _ in existing_results:
            seen_sectors.add(existing_deal.metadata.sector)
            seen_geographies.add(existing_deal.metadata.geography)
            seen_companies.add(existing_deal.metadata.company_name)
        
        adjusted_score = score
        
        # Penalize if same sector already seen
        if metadata.sector in seen_sectors:
            adjusted_score *= (1.0 - penalty_factor * 0.5)
        
        # Penalize if same geography already seen
        if metadata.geography in seen_geographies:
            adjusted_score *= (1.0 - penalty_factor * 0.3)
        
        # Strong penalty for same company
        if metadata.company_name in seen_companies:
            adjusted_score *= (1.0 - penalty_factor * 0.8)
        
        return adjusted_score
    
    def _calculate_recency_boost(self, deal_year: int, current_year: int) -> float:
        """
        Calculate recency boost for deal.
        
        More recent deals get higher boost. Boost decays exponentially
        with age (5-year half-life).
        
        Args:
            deal_year: Year of the deal
            current_year: Current year
            
        Returns:
            Recency boost factor [0.0, 1.0]
        """
        age_years = current_year - deal_year
        
        if age_years <= 0:
            return 1.0  # Future or current year
        
        # Exponential decay: boost = exp(-age / half_life)
        half_life = 5.0
        boost = 1.0 / (1.0 + age_years / half_life)
        
        return boost
    
    def _calculate_feedback_boost(self, deal_id: str) -> float:
        """
        Calculate feedback-based boost for deal.
        
        Deals that have received positive feedback get boosted.
        
        Args:
            deal_id: Deal identifier
            
        Returns:
            Feedback boost factor [0.0, 1.0]
        """
        if not self.enable_feedback_boost:
            return 0.0
        
        try:
            if self._feedback_logger is None:
                from src.feedback.feedback_logger import FeedbackLogger
                self._feedback_logger = FeedbackLogger()
            
            stats = self._feedback_logger.get_feedback_stats()
            if stats["total_feedback"] == 0:
                return 0.0
            
            # Get feedback for this specific deal
            positive_pairs = self._feedback_logger.get_positive_pairs()
            negative_pairs = self._feedback_logger.get_negative_pairs()
            
            positive_count = sum(1 for _, rid in positive_pairs if rid == deal_id)
            negative_count = sum(1 for _, rid in negative_pairs if rid == deal_id)
            
            if positive_count + negative_count == 0:
                return 0.0
            
            # Boost based on positive feedback ratio
            positive_ratio = positive_count / (positive_count + negative_count)
            boost = positive_ratio * 0.5  # Max 0.5 boost
            
            return boost
        
        except Exception as e:
            logger.warning(f"Error calculating feedback boost: {e}")
            return 0.0
    
    def _calculate_personalization_boost(
        self,
        deal: Deal,
        analyst_id: str
    ) -> float:
        """
        Calculate personalization boost based on analyst preferences.
        
        This is a placeholder for personalization logic. In production,
        this would query analyst-specific preferences, past selections,
        and sector/deal type preferences.
        
        Args:
            deal: Deal to evaluate
            analyst_id: Analyst identifier
            
        Returns:
            Personalization boost factor [0.0, 1.0]
        """
        # Placeholder: return 0 for now
        # In production, would query analyst preferences database
        # and compute boost based on:
        # - Preferred sectors
        # - Preferred deal types
        # - Past deal selections
        # - Team/fund alignment
        return 0.0
    
    def add_diversity_penalty(
        self,
        results: List[Tuple[Deal, float, Dict[str, float]]],
        penalty_factor: float = 0.1
    ) -> List[Tuple[Deal, float, Dict[str, float]]]:
        """
        Apply diversity penalty to reduce duplicate results.
        
        This is a legacy method for backward compatibility.
        New code should use rank_results() which includes diversity penalty.
        
        Args:
            results: List of (deal, score, breakdown) tuples
            penalty_factor: Strength of diversity penalty (0-1)
            
        Returns:
            Re-ranked results with diversity adjustments
        """
        enhanced = []
        for deal, score, breakdown in results:
            adjusted_score = self._apply_diversity_penalty(
                deal, score, enhanced, penalty_factor
            )
            enhanced.append((deal, adjusted_score, breakdown))
        
        enhanced.sort(key=lambda x: x[1], reverse=True)
        return enhanced
    
    def should_trigger_fallback(
        self,
        results: List[Tuple[Deal, float, Dict[str, float]]]
    ) -> bool:
        """
        Determine if fallback handler should be triggered.
        
        Fallback is triggered when:
        - No results above similarity threshold
        - Top result score is below threshold
        
        Args:
            results: List of (deal, score, breakdown) tuples
            
        Returns:
            True if fallback should be triggered
        """
        if not results:
            return True
        
        top_score = max(r[1] for r in results)
        return top_score < self.similarity_threshold


