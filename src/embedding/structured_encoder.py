"""
Structured features encoder.

This module handles encoding of structured financial and business metrics
into normalized feature vectors suitable for similarity comparison.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Any
import logging
from sklearn.preprocessing import StandardScaler
import math

from src.models.deal import Deal, StructuredFeatures

logger = logging.getLogger(__name__)


class StructuredEncoder:
    """
    Encoder for structured deal features.
    
    This class handles:
    - Normalization of financial metrics (log transforms, z-scores)
    - Categorical encoding (sectors, deal types)
    - Temporal feature encoding
    - Creation of unified feature vectors
    """
    
    def __init__(self):
        """Initialize structured encoder."""
        self.scaler = StandardScaler()
        self.sector_embeddings: Dict[str, List[float]] = {}
        self.deal_type_embeddings: Dict[str, List[float]] = {}
        self.fitted = False
        
        # Initialize simple sector embeddings (can be learned later)
        self._initialize_categorical_embeddings()
    
    def _initialize_categorical_embeddings(self):
        """Initialize simple categorical embeddings."""
        sectors = ["Software", "Healthcare IT", "Financial Technology", 
                  "E-commerce", "Business Services", "Manufacturing"]
        
        # Simple one-hot like embeddings (can be replaced with learned embeddings)
        for i, sector in enumerate(sectors):
            embedding = [0.0] * len(sectors)
            embedding[i] = 1.0
            self.sector_embeddings[sector] = embedding
        
        deal_types = ["Growth", "Buyout", "Minority", "Majority"]
        for i, deal_type in enumerate(deal_types):
            embedding = [0.0] * len(deal_types)
            embedding[i] = 1.0
            self.deal_type_embeddings[deal_type] = embedding
    
    def normalize_revenue(self, revenue: Optional[float]) -> float:
        """
        Apply log transform to revenue for normalization.
        
        Args:
            revenue: Revenue in USD
            
        Returns:
            Log-normalized revenue or 0 if None
        """
        if revenue is None or revenue <= 0:
            return 0.0
        
        return math.log10(revenue + 1.0)  # +1 to handle zero
    
    def normalize_ebitda(self, ebitda: Optional[float]) -> float:
        """
        Apply log transform to EBITDA for normalization.
        
        Args:
            ebitda: EBITDA in USD
            
        Returns:
            Log-normalized EBITDA or 0 if None
        """
        if ebitda is None:
            return 0.0
        
        # Handle negative EBITDA
        return math.log10(abs(ebitda) + 1.0) * (1.0 if ebitda >= 0 else -1.0)
    
    def normalize_growth_rate(self, growth_rate: Optional[float]) -> float:
        """
        Normalize growth rate (already bounded, just clip).
        
        Args:
            growth_rate: Growth rate as decimal (e.g., 0.25 for 25%)
            
        Returns:
            Normalized growth rate
        """
        if growth_rate is None:
            return 0.0
        
        # Clip to reasonable range [-1, 2] (i.e., -100% to +200%)
        return max(-1.0, min(2.0, float(growth_rate)))
    
    def normalize_margin(self, margin: Optional[float]) -> float:
        """
        Normalize margin (already bounded between -1 and 1).
        
        Args:
            margin: Margin as decimal (e.g., 0.15 for 15%)
            
        Returns:
            Normalized margin
        """
        if margin is None:
            return 0.0
        
        # Clip to reasonable range [-1, 1]
        return max(-1.0, min(1.0, float(margin)))
    
    def get_sector_embedding(self, sector: str) -> List[float]:
        """
        Get embedding for sector.
        
        Args:
            sector: Sector name
            
        Returns:
            Sector embedding vector
        """
        if sector in self.sector_embeddings:
            return self.sector_embeddings[sector]
        
        # Default embedding for unknown sectors
        return [0.0] * len(list(self.sector_embeddings.values())[0])
    
    def get_deal_type_embedding(self, deal_type: str) -> List[float]:
        """
        Get embedding for deal type.
        
        Args:
            deal_type: Deal type name
            
        Returns:
            Deal type embedding vector
        """
        if deal_type in self.deal_type_embeddings:
            return self.deal_type_embeddings[deal_type]
        
        # Default embedding
        return [0.0] * len(list(self.deal_type_embeddings.values())[0])
    
    def encode_temporal_features(self, deal_year: int) -> List[float]:
        """
        Encode temporal features (year, macro regime).
        
        Args:
            deal_year: Year of the deal
            
        Returns:
            Temporal feature vector [year_normalized, pre_covid, covid, post_covid, low_rates]
        """
        # Normalize year (assume range 2010-2030)
        year_normalized = (deal_year - 2010) / 20.0
        
        # Macro regime flags
        pre_covid = 1.0 if deal_year < 2020 else 0.0
        covid = 1.0 if 2020 <= deal_year <= 2022 else 0.0
        post_covid = 1.0 if deal_year > 2022 else 0.0
        
        # Interest rate environment (simplified)
        low_rates = 1.0 if deal_year < 2022 else 0.0
        
        return [year_normalized, pre_covid, covid, post_covid, low_rates]
    
    def encode_features(self, deal: Deal) -> List[float]:
        """
        Encode all structured features into a single vector.
        
        Args:
            deal: Deal object with structured features
            
        Returns:
            Normalized feature vector
        """
        features = []
        sf = deal.structured_features
        
        # Normalize financial metrics
        features.append(self.normalize_revenue(sf.revenue))
        features.append(self.normalize_ebitda(sf.ebitda))
        features.append(self.normalize_growth_rate(sf.growth_rate))
        features.append(self.normalize_margin(sf.margin))
        features.append(self.normalize_revenue(sf.enterprise_value) if sf.enterprise_value else 0.0)
        
        # Additional metrics
        features.append(float(sf.leverage) if sf.leverage is not None else 0.0)
        features.append(self.normalize_revenue(sf.free_cash_flow) if sf.free_cash_flow else 0.0)
        
        # Categorical embeddings
        sector_emb = self.get_sector_embedding(deal.metadata.sector)
        features.extend(sector_emb)
        
        deal_type_emb = self.get_deal_type_embedding(deal.metadata.deal_type)
        features.extend(deal_type_emb)
        
        # Temporal features
        temporal = self.encode_temporal_features(deal.metadata.deal_year)
        features.extend(temporal)
        
        return features
    
    def fit(self, deals: List[Deal]) -> None:
        """
        Fit encoder on a set of deals (for scaling).
        
        Args:
            deals: List of Deal objects to fit on
        """
        if not deals:
            logger.warning("No deals provided for fitting")
            return
        
        # Extract feature vectors
        feature_matrix = np.array([self.encode_features(deal) for deal in deals])
        
        # Fit scaler
        self.scaler.fit(feature_matrix)
        self.fitted = True
        
        logger.info(f"Fitted structured encoder on {len(deals)} deals")
    
    def transform(self, deal: Deal) -> np.ndarray:
        """
        Transform deal to normalized feature vector.
        
        Args:
            deal: Deal object
            
        Returns:
            Normalized feature vector
        """
        features = np.array(self.encode_features(deal)).reshape(1, -1)
        
        if self.fitted:
            features = self.scaler.transform(features)
        
        # Store in deal for later use
        deal.structured_features.normalized_vector = features.flatten().tolist()
        
        return features.flatten()


