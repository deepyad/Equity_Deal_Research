"""
Storage layer for the Deal Similarity System.

This package handles data persistence:
- Vector database for embeddings (FAISS)
- Metadata storage (SQLite/PostgreSQL)
"""

from .vector_store import VectorStore
from .metadata_store import MetadataStore

__all__ = ["VectorStore", "MetadataStore"]


