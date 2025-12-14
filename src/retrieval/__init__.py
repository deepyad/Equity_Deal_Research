"""
Retrieval and ranking module for the Deal Similarity System.

This package handles:
- Query preprocessing and context identification
- Similarity search and scoring
- Result ranking and filtering
- Context-aware retrieval

According to the consolidated document, the retrieval layer includes:
- Query Preprocessor: Extract metadata, parse documents, identify context (Decision Point D2)
- Similarity Calculator: Structured/text/metadata similarity computation
- Result Ranker: Diversity penalty, recency boost, feedback boost, personalization (Decision Point D3)
"""

from .similarity import SimilarityCalculator
from .ranker import ResultRanker
from .query_preprocessor import QueryPreprocessor, QueryType, QueryContext

__all__ = [
    "SimilarityCalculator",
    "ResultRanker",
    "QueryPreprocessor",
    "QueryType",
    "QueryContext"
]


