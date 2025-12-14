"""
Multi-modal fusion strategies.

This module handles combining structured and text embeddings
into unified representations for similarity search.
"""

import numpy as np
from typing import Dict, List, Optional, Tuple
import logging

from src.models.deal import Deal
from src.utils.config import get_config

logger = logging.getLogger(__name__)


class MultiModalFusion:
    """
    Multi-modal fusion for combining structured and text embeddings.
    
    Supports multiple fusion strategies:
    - Late fusion: Weighted combination of similarity scores
    - Early fusion: Concatenation and projection
    - Context-aware: Different weights for different use cases
    """
    
    def __init__(self, context: str = "default"):
        """
        Initialize multi-modal fusion.
        
        Args:
            context: Similarity context (default, screening, risk_assessment, etc.)
        """
        self.context = context
        self.weights = self._load_weights(context)
    
    def _load_weights(self, context: str) -> Dict[str, float]:
        """
        Load fusion weights for given context.
        
        Args:
            context: Similarity context
            
        Returns:
            Dictionary with weight values
        """
        config = get_config()
        similarity_config = config.get_similarity_config()
        
        contexts = similarity_config.get("contexts", {})
        
        if context in contexts:
            weights = contexts[context]
        else:
            weights = similarity_config.get("default_weights", {
                "structured": 0.4,
                "text": 0.6,
                "metadata": 0.1
            })
        
        return weights
    
    def compute_structured_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """
        Compute structured feature similarity (normalized Euclidean).
        
        Args:
            vec1: Structured feature vector 1
            vec2: Structured feature vector 2
            
        Returns:
            Similarity score [0, 1]
        """
        if vec1 is None or vec2 is None:
            return 0.0
        
        vec1 = np.array(vec1)
        vec2 = np.array(vec2)
        
        # Ensure same dimension
        min_dim = min(len(vec1), len(vec2))
        vec1 = vec1[:min_dim]
        vec2 = vec2[:min_dim]
        
        # Normalized Euclidean distance
        distance = np.linalg.norm(vec1 - vec2)
        dimension = len(vec1)
        
        if dimension == 0:
            return 0.0
        
        # Normalize to [0, 1] range
        normalized_distance = distance / (np.sqrt(dimension) + 1e-10)
        similarity = 1.0 - min(1.0, normalized_distance)
        
        return float(similarity)
    
    def compute_text_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """
        Compute text embedding similarity (cosine similarity).
        
        Args:
            vec1: Text embedding vector 1
            vec2: Text embedding vector 2
            
        Returns:
            Cosine similarity score [-1, 1], normalized to [0, 1]
        """
        if vec1 is None or vec2 is None:
            return 0.0
        
        vec1 = np.array(vec1)
        vec2 = np.array(vec2)
        
        # Ensure same dimension
        min_dim = min(len(vec1), len(vec2))
        vec1 = vec1[:min_dim]
        vec2 = vec2[:min_dim]
        
        # Cosine similarity
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        cosine_sim = dot_product / (norm1 * norm2 + 1e-10)
        
        # Normalize from [-1, 1] to [0, 1]
        similarity = (cosine_sim + 1.0) / 2.0
        
        return float(similarity)
    
    def compute_metadata_similarity(self, deal1: Deal, deal2: Deal) -> float:
        """
        Compute metadata similarity score.
        
        Args:
            deal1: First deal
            deal2: Second deal
            
        Returns:
            Metadata similarity score [0, 1]
        """
        score = 0.0
        m1 = deal1.metadata
        m2 = deal2.metadata
        
        # Sector match (0.2 weight)
        if m1.sector == m2.sector:
            score += 0.2
        
        # Geography alignment (0.1 weight)
        if m1.geography == m2.geography:
            score += 0.1
        
        # Deal type match
        if m1.deal_type == m2.deal_type:
            score += 0.1
        
        # Recency decay (exponential)
        year_diff = abs(m1.deal_year - m2.deal_year)
        recency_score = np.exp(-year_diff / 5.0)  # Decay over 5 years
        score += 0.1 * recency_score
        
        return min(1.0, score)
    
    def fuse_similarities(self, struct_sim: float, text_sim: float,
                         meta_sim: float) -> float:
        """
        Fuse multiple similarity scores using weighted combination.
        
        Args:
            struct_sim: Structured similarity score
            text_sim: Text similarity score
            meta_sim: Metadata similarity score
            
        Returns:
            Fused similarity score
        """
        w_struct = self.weights.get("structured", 0.4)
        w_text = self.weights.get("text", 0.6)
        w_meta = self.weights.get("metadata", 0.1)
        
        # Normalize weights
        total_weight = w_struct + w_text + w_meta
        if total_weight > 0:
            w_struct /= total_weight
            w_text /= total_weight
            w_meta /= total_weight
        
        fused_score = (
            w_struct * struct_sim +
            w_text * text_sim +
            w_meta * meta_sim
        )
        
        return min(1.0, max(0.0, fused_score))
    
    def compute_similarity(self, deal1: Deal, deal2: Deal) -> Tuple[float, Dict[str, float]]:
        """
        Compute overall similarity between two deals.
        
        Args:
            deal1: First deal
            deal2: Second deal
            
        Returns:
            Tuple of (overall similarity score, breakdown dictionary)
        """
        # Structured similarity
        struct_vec1 = deal1.structured_features.normalized_vector
        struct_vec2 = deal2.structured_features.normalized_vector
        
        struct_sim = 0.0
        if struct_vec1 and struct_vec2:
            struct_sim = self.compute_structured_similarity(
                np.array(struct_vec1),
                np.array(struct_vec2)
            )
        
        # Text similarity
        text_vec1 = deal1.text_embeddings.get_primary_embedding()
        text_vec2 = deal2.text_embeddings.get_primary_embedding()
        
        text_sim = 0.0
        if text_vec1 and text_vec2:
            text_sim = self.compute_text_similarity(
                np.array(text_vec1),
                np.array(text_vec2)
            )
        
        # Metadata similarity
        meta_sim = self.compute_metadata_similarity(deal1, deal2)
        
        # Fuse similarities
        overall_sim = self.fuse_similarities(struct_sim, text_sim, meta_sim)
        
        breakdown = {
            "structured": struct_sim,
            "text": text_sim,
            "metadata": meta_sim,
            "overall": overall_sim
        }
        
        return overall_sim, breakdown


