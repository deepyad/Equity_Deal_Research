"""
Text embedding encoder.

This module handles generation of text embeddings from document content
using transformer models (sentence-transformers).
"""

import logging
from typing import List, Optional, Dict
from pathlib import Path
import numpy as np

# Initialize logger before using it
logger = logging.getLogger(__name__)

# ============================================================================
# TEXT EMBEDDING FEATURE FLAG
# ============================================================================
# Set to False to disable text embeddings (allows app to run without 
# sentence-transformers installed). When disabled, only structured features
# will be used for similarity search.
# 
# To enable text embeddings:
#   1. Install sentence-transformers: pip install sentence-transformers
#   2. Set ENABLE_TEXT_EMBEDDINGS = True
# ============================================================================
ENABLE_TEXT_EMBEDDINGS = False  # Currently DISABLED - only structured features will be used

try:
    if ENABLE_TEXT_EMBEDDINGS:
        from sentence_transformers import SentenceTransformer
        SENTENCE_TRANSFORMERS_AVAILABLE = True
    else:
        SENTENCE_TRANSFORMERS_AVAILABLE = False
        logger.info("Text embeddings are DISABLED (ENABLE_TEXT_EMBEDDINGS = False). "
                   "Only structured features will be used for similarity search.")
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    logger.warning("sentence-transformers not available. Text embeddings disabled. "
                  "Install with: pip install sentence-transformers")

from src.models.deal import Deal, TextEmbeddings
from src.utils.config import get_config


class TextEncoder:
    """
    Encoder for text content using transformer models.
    
    This class handles:
    - Text embedding generation using sentence-transformers
    - Section-level embeddings (business, market, financial)
    - Document-level embeddings (CIM overall, investment memos)
    - Batch processing for efficiency
    """
    
    def __init__(self, model_name: Optional[str] = None):
        """
        Initialize text encoder.
        
        Args:
            model_name: Name of sentence-transformers model to use.
                       If None, loads from config.
                       
        Note:
            If ENABLE_TEXT_EMBEDDINGS is False or sentence-transformers is not
            available, this will create a dummy encoder that returns zero vectors.
        """
        # Check if text embeddings should be enabled
        if not SENTENCE_TRANSFORMERS_AVAILABLE or not ENABLE_TEXT_EMBEDDINGS:
            logger.warning(
                "TextEncoder initialized without sentence-transformers. "
                "Text embeddings will be disabled. Set ENABLE_TEXT_EMBEDDINGS = True "
                "and install sentence-transformers to enable."
            )
            self.model = None
            self.dimension = 384  # Default dimension for compatibility
            self.model_name = None
            return
        
        # Normal initialization when text embeddings are enabled
        if model_name is None:
            config = get_config()
            model_name = config.get("embedding.model_name", "all-MiniLM-L6-v2")
        
        self.model_name = model_name
        logger.info(f"Loading text encoder model: {model_name}")
        
        try:
            self.model = SentenceTransformer(model_name)
            self.dimension = self.model.get_sentence_embedding_dimension()
            logger.info(f"Model loaded. Embedding dimension: {self.dimension}")
        except Exception as e:
            logger.error(f"Failed to load model {model_name}: {e}")
            raise
    
    def encode_text(self, text: str) -> List[float]:
        """
        Encode a single text string into an embedding vector.
        
        Args:
            text: Text content to encode
            
        Returns:
            Embedding vector (zero vector if text embeddings are disabled)
        """
        # If text embeddings are disabled, return zero vector
        if not SENTENCE_TRANSFORMERS_AVAILABLE or not ENABLE_TEXT_EMBEDDINGS or self.model is None:
            logger.debug("Text embeddings disabled, returning zero vector")
            return [0.0] * self.dimension
        
        if not text or not text.strip():
            # Return zero vector if empty
            return [0.0] * self.dimension
        
        try:
            # Truncate very long texts (model limit)
            max_length = 512  # Typical token limit
            if len(text) > max_length * 4:  # Rough char estimate
                text = text[:max_length * 4]
            
            embedding = self.model.encode(text, convert_to_numpy=True)
            return embedding.tolist()
        
        except Exception as e:
            logger.error(f"Error encoding text: {e}")
            return [0.0] * self.dimension
    
    def encode_batch(self, texts: List[str], batch_size: int = 32) -> List[List[float]]:
        """
        Encode multiple texts in batch for efficiency.
        
        Args:
            texts: List of text strings to encode
            batch_size: Batch size for processing
            
        Returns:
            List of embedding vectors (zero vectors if text embeddings are disabled)
        """
        # If text embeddings are disabled, return zero vectors
        if not SENTENCE_TRANSFORMERS_AVAILABLE or not ENABLE_TEXT_EMBEDDINGS or self.model is None:
            logger.debug("Text embeddings disabled, returning zero vectors")
            return [[0.0] * self.dimension for _ in texts]
        
        if not texts:
            return []
        
        try:
            config = get_config()
            batch_size = config.get("embedding.batch_size", batch_size)
            
            embeddings = self.model.encode(
                texts,
                batch_size=batch_size,
                convert_to_numpy=True,
                show_progress_bar=False
            )
            
            return embeddings.tolist()
        
        except Exception as e:
            logger.error(f"Error encoding batch: {e}")
            # Fallback to individual encoding
            return [self.encode_text(text) for text in texts]
    
    def encode_deal_documents(self, deal: Deal, cim_text: Optional[str] = None,
                            memo_text: Optional[str] = None,
                            notes_text: Optional[str] = None) -> TextEmbeddings:
        """
        Encode all text documents for a deal.
        
        Args:
            deal: Deal object to encode
            cim_text: CIM document text
            memo_text: Investment memo text
            notes_text: Analyst notes text
            
        Returns:
            TextEmbeddings object with all embeddings
        """
        text_embeddings = deal.text_embeddings or TextEmbeddings()
        
        # Encode CIM overall
        if cim_text:
            text_embeddings.cim_overall = self.encode_text(cim_text)
        
        # Encode investment memo (higher priority)
        if memo_text:
            text_embeddings.ic_memo = self.encode_text(memo_text)
        
        # Encode analyst notes
        if notes_text:
            text_embeddings.notes = self.encode_text(notes_text)
        
        # Encode sections if CIM text is available
        if cim_text:
            sections = self._extract_sections(cim_text)
            
            if sections.get("business_overview"):
                text_embeddings.business_section = self.encode_text(
                    sections["business_overview"]
                )
            
            if sections.get("market"):
                text_embeddings.market_section = self.encode_text(
                    sections["market"]
                )
            
            if sections.get("financial"):
                text_embeddings.financial_section = self.encode_text(
                    sections["financial"]
                )
        
        # Extract qualitative tags using TagExtractor
        if cim_text or memo_text:
            try:
                from src.embedding.tag_extractor import TagExtractor
                tag_extractor = TagExtractor()
                combined_text = (cim_text or "") + " " + (memo_text or "")
                text_embeddings.qualitative_tags = tag_extractor.extract_tags(combined_text)
            except Exception as e:
                logger.warning(f"Failed to extract tags: {e}, using fallback method")
                text_embeddings.qualitative_tags = self._extract_tags(
                    cim_text or "" + " " + (memo_text or "")
                )
        
        return text_embeddings
    
    def _extract_sections(self, text: str) -> Dict[str, str]:
        """
        Extract document sections from text (simplified).
        
        Args:
            text: Full document text
            
        Returns:
            Dictionary mapping section names to text
        """
        sections = {
            "business_overview": "",
            "market": "",
            "financial": ""
        }
        
        # Simple keyword-based section extraction
        keywords = {
            "business_overview": ["business overview", "company overview", "about"],
            "market": ["market", "industry", "competitive"],
            "financial": ["financial", "revenue", "ebitda", "profit"]
        }
        
        lines = text.split("\n")
        current_section = None
        current_text = []
        
        for line in lines:
            line_lower = line.lower()
            
            # Check if line is a section header
            for section, section_keywords in keywords.items():
                if any(kw in line_lower for kw in section_keywords) and len(line) < 100:
                    if current_section:
                        sections[current_section] = "\n".join(current_text)
                    current_section = section
                    current_text = []
                    break
            
            if current_section:
                current_text.append(line)
        
        # Save last section
        if current_section and current_text:
            sections[current_section] = "\n".join(current_text)
        
        return sections
    
    def _extract_tags(self, text: str) -> List[str]:
        """
        Extract qualitative tags from text (simplified).
        
        Args:
            text: Text content
            
        Returns:
            List of qualitative tags
        """
        tags = []
        text_lower = text.lower()
        
        # Simple keyword-based tag extraction
        tag_keywords = {
            "high_churn_risk": ["churn", "customer retention", "attrition"],
            "usage_pricing": ["usage-based", "pay per use", "consumption"],
            "recurring_revenue": ["recurring", "subscription", "mrr", "arr"],
            "b2b": ["b2b", "business to business", "enterprise"],
            "regulated": ["regulated", "regulation", "compliance", "fda"],
            "platform": ["platform", "marketplace", "network effects"]
        }
        
        for tag, keywords in tag_keywords.items():
            if any(kw in text_lower for kw in keywords):
                tags.append(tag)
        
        return tags
    
    def get_primary_embedding(self, text_embeddings: TextEmbeddings) -> Optional[List[float]]:
        """
        Get the primary text embedding for a deal (for similarity search).
        
        Priority: ic_memo > business_section > cim_overall
        
        Args:
            text_embeddings: TextEmbeddings object
            
        Returns:
            Primary embedding vector or None
        """
        return text_embeddings.get_primary_embedding()


