"""
Vector store for embedding storage and similarity search.

This module uses FAISS for efficient approximate nearest neighbor search
of deal embeddings.
"""

import logging
import numpy as np
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any
import pickle

# Initialize logger before using it
logger = logging.getLogger(__name__)

# ============================================================================
# FAISS FEATURE FLAG
# ============================================================================
# Set to False to disable FAISS vector store (allows app to run without 
# faiss-cpu installed). When disabled, a simple in-memory vector store
# will be used with basic similarity search.
# 
# To enable FAISS vector store:
#   1. Install FAISS: pip install faiss-cpu (or faiss-gpu for GPU support)
#   2. Set ENABLE_FAISS = True
# ============================================================================
ENABLE_FAISS = False  # Currently DISABLED - using simple in-memory vector store

try:
    if ENABLE_FAISS:
        import faiss
        FAISS_AVAILABLE = True
    else:
        FAISS_AVAILABLE = False
        logger.info("FAISS is DISABLED (ENABLE_FAISS = False). "
                   "Using simple in-memory vector store.")
except ImportError:
    FAISS_AVAILABLE = False
    logger.warning("FAISS not available. Using simple in-memory vector store. "
                  "Install with: pip install faiss-cpu")

from src.models.deal import Deal
from src.utils.config import get_config


class VectorStore:
    """
    Vector database for storing and searching deal embeddings.
    
    Uses FAISS for efficient similarity search. Supports:
    - Adding deals with embeddings
    - Similarity search (top-k nearest neighbors)
    - Persistence to disk
    - Incremental updates
    """
    
    def __init__(self, dimension: Optional[int] = None, index_path: Optional[str] = None):
        """
        Initialize vector store.
        
        Args:
            dimension: Embedding dimension
            index_path: Path to save/load FAISS index
        """
        # Check if FAISS should be enabled
        if not FAISS_AVAILABLE or not ENABLE_FAISS:
            logger.warning(
                "VectorStore initialized without FAISS. "
                "Using simple in-memory storage. Set ENABLE_FAISS = True "
                "and install faiss-cpu to enable FAISS vector store."
            )
            # Initialize simple in-memory storage
            self.use_faiss = False
            self.vectors: Dict[str, np.ndarray] = {}
            self.deal_ids: List[str] = []
            if dimension is None:
                config = get_config()
                vector_config = config.get_vector_store_config()
                dimension = vector_config.get("dimension", 384)
            self.dimension = dimension
            self.index_path = Path(index_path) if index_path else None
            self.index = None
            return
        
        # Normal initialization when FAISS is enabled
        self.use_faiss = True
        
        if dimension is None:
            config = get_config()
            vector_config = config.get_vector_store_config()
            dimension = vector_config.get("dimension", 384)
        
        if index_path is None:
            config = get_config()
            vector_config = config.get_vector_store_config()
            index_path = vector_config.get("index_path", "data/vectors/deal_index.faiss")
        
        self.dimension = dimension
        self.index_path = Path(index_path)
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        
        # FAISS index
        self.index: Optional[faiss.Index] = None
        self.deal_ids: List[str] = []  # Mapping from index position to deal_id
        
        # Load existing index if available
        self._load_index()
        
        # If no index exists, create new one
        if self.index is None:
            self._create_index()
    
    def _create_index(self):
        """Create a new FAISS index."""
        if not self.use_faiss:
            return  # No-op when FAISS is disabled
        logger.info(f"Creating new FAISS index with dimension {self.dimension}")
        
        # Use L2 distance (Euclidean) - can be converted to cosine with normalization
        self.index = faiss.IndexFlatL2(self.dimension)
        self.deal_ids = []
        
        logger.info("FAISS index created")
    
    def _load_index(self):
        """Load FAISS index from disk."""
        if not self.use_faiss:
            return  # No-op when FAISS is disabled
        index_file = self.index_path
        ids_file = self.index_path.with_suffix('.ids')
        
        if not index_file.exists():
            logger.info("No existing index found, will create new one")
            return
        
        try:
            logger.info(f"Loading FAISS index from {index_file}")
            self.index = faiss.read_index(str(index_file))
            
            if ids_file.exists():
                with open(ids_file, 'rb') as f:
                    self.deal_ids = pickle.load(f)
            
            logger.info(f"Loaded index with {self.index.ntotal} vectors")
        
        except Exception as e:
            logger.error(f"Error loading index: {e}")
            self.index = None
            self.deal_ids = []
    
    def _save_index(self):
        """Save FAISS index to disk."""
        if not self.use_faiss or self.index is None:
            return  # No-op when FAISS is disabled or index doesn't exist
        
        try:
            logger.info(f"Saving FAISS index to {self.index_path}")
            faiss.write_index(self.index, str(self.index_path))
            
            ids_file = self.index_path.with_suffix('.ids')
            with open(ids_file, 'wb') as f:
                pickle.dump(self.deal_ids, f)
            
            logger.info("Index saved successfully")
        
        except Exception as e:
            logger.error(f"Error saving index: {e}")
    
    def add_deal(self, deal: Deal, embedding: np.ndarray):
        """
        Add a deal embedding to the vector store.
        
        Args:
            deal: Deal object
            embedding: Embedding vector (must match dimension)
        """
        if self.index is None:
            self._create_index()
        
        embedding = np.array(embedding, dtype=np.float32)
        
        # Ensure correct dimension
        if embedding.shape[0] != self.dimension:
            raise ValueError(
                f"Embedding dimension {embedding.shape[0]} doesn't match "
                f"index dimension {self.dimension}"
            )
        
        # Reshape to 2D (1 x dimension)
        embedding = embedding.reshape(1, -1)
        
        # Add to index
        self.index.add(embedding)
        self.deal_ids.append(deal.metadata.deal_id)
        
        logger.debug(f"Added deal {deal.metadata.deal_id} to vector store")
    
    def add_deals_batch(self, deals: List[Deal], embeddings: np.ndarray):
        """
        Add multiple deals in batch (more efficient).
        
        Args:
            deals: List of Deal objects
            embeddings: Numpy array of shape (n_deals, dimension)
        """
        embeddings = np.array(embeddings, dtype=np.float32)
        
        if embeddings.shape[1] != self.dimension:
            raise ValueError(
                f"Embedding dimension {embeddings.shape[1]} doesn't match "
                f"index dimension {self.dimension}"
            )
        
        # If FAISS is not enabled, use simple in-memory storage
        if not self.use_faiss:
            for i, deal in enumerate(deals):
                self.vectors[deal.metadata.deal_id] = embeddings[i]
                if deal.metadata.deal_id not in self.deal_ids:
                    self.deal_ids.append(deal.metadata.deal_id)
            logger.info(f"Added {len(deals)} deals to simple vector store")
            return
        
        # FAISS-based storage
        if self.index is None:
            self._create_index()
        
        # Add to index
        self.index.add(embeddings)
        self.deal_ids.extend([deal.metadata.deal_id for deal in deals])
        
        logger.info(f"Added {len(deals)} deals to FAISS vector store")
    
    def search(self, query_embedding: np.ndarray, top_k: int = 10) -> List[Tuple[str, float]]:
        """
        Search for similar deals.
        
        Args:
            query_embedding: Query embedding vector
            top_k: Number of results to return
            
        Returns:
            List of (deal_id, distance) tuples, sorted by distance
        """
        query_embedding = np.array(query_embedding, dtype=np.float32)
        
        if query_embedding.shape[0] != self.dimension:
            raise ValueError(
                f"Query embedding dimension {query_embedding.shape[0]} doesn't match "
                f"index dimension {self.dimension}"
            )
        
        # If FAISS is not enabled, use simple cosine similarity search
        if not self.use_faiss:
            if not self.vectors:
                logger.warning("Vector store is empty, returning no results")
                return []
            
            # Calculate cosine similarity for all vectors
            query_norm = np.linalg.norm(query_embedding)
            if query_norm == 0:
                return []
            
            similarities = []
            for deal_id, vector in self.vectors.items():
                vector_norm = np.linalg.norm(vector)
                if vector_norm == 0:
                    continue
                # Cosine similarity
                similarity = np.dot(query_embedding, vector) / (query_norm * vector_norm)
                # Convert to distance (1 - similarity)
                distance = 1.0 - similarity
                similarities.append((deal_id, float(distance)))
            
            # Sort by distance and return top_k
            similarities.sort(key=lambda x: x[1])
            return similarities[:top_k]
        
        # FAISS-based search
        if self.index is None or self.index.ntotal == 0:
            logger.warning("FAISS index is empty, returning no results")
            return []
        
        # Reshape to 2D
        query_embedding = query_embedding.reshape(1, -1)
        
        # Search
        distances, indices = self.index.search(query_embedding, min(top_k, self.index.ntotal))
        
        # Convert to list of (deal_id, distance)
        results = []
        for i, idx in enumerate(indices[0]):
            if idx < len(self.deal_ids):
                deal_id = self.deal_ids[idx]
                distance = float(distances[0][i])
                results.append((deal_id, distance))
        
        return results
    
    def get_total_deals(self) -> int:
        """Get total number of deals in the store."""
        if not self.use_faiss:
            return len(self.vectors)
        if self.index is None:
            return 0
        return self.index.ntotal
    
    def save(self):
        """Save the index to disk."""
        if self.use_faiss:
            self._save_index()
        else:
            logger.debug("Simple vector store (no persistence needed)")
    
    def clear(self):
        """Clear all vectors from the store."""
        if self.use_faiss:
            self._create_index()
        else:
            self.vectors = {}
            self.deal_ids = []
        logger.info("Vector store cleared")


