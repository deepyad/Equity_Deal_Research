"""
Embedding generation module for the Deal Similarity System.

This package handles creation of multi-modal embeddings:
- Structured feature encoding (financial metrics)
- Text embeddings (document content)
- Tag extraction (qualitative patterns)
- Multi-modal fusion strategies

According to the consolidated document, the embedding service includes:
- Structured Encoder: Financial normalization, log/z-score transforms, categorical embeddings, temporal features
- Text Encoder: Sentence-transformers/FinBERT, section-level embeddings, IC memo weighting
- Tag Extractor: Pattern recognition, qualitative tags, risk indicators
- Multi-Modal Fusion: Joint/late fusion, weight combination, context-specific heads
"""

from .structured_encoder import StructuredEncoder
from .text_encoder import TextEncoder
from .fusion import MultiModalFusion
from .tag_extractor import TagExtractor

__all__ = ["StructuredEncoder", "TextEncoder", "MultiModalFusion", "TagExtractor"]


