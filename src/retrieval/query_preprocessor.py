"""
Query preprocessor for similarity search.

This module handles preprocessing of queries before similarity search,
including metadata extraction, document parsing, and context identification.

According to the consolidated document, this module:
- Extracts metadata from query input
- Parses documents if provided
- Identifies context (screening, risk assessment, exit potential, strategic fit)
- Routes to appropriate encoder based on query type (Decision Point D2)
"""

import logging
from typing import Dict, Optional, List, Tuple
from enum import Enum

from src.models.deal import Deal, DealMetadata, StructuredFeatures, TextEmbeddings
from src.ingestion.pdf_extractor import PDFExtractor

logger = logging.getLogger(__name__)


class QueryContext(Enum):
    """Query context types for similarity search."""
    DEFAULT = "default"
    SCREENING = "screening"  # Focus on financial similarity
    RISK_ASSESSMENT = "risk_assessment"  # Focus on risk patterns
    EXIT_POTENTIAL = "exit_potential"  # Focus on exit outcomes
    STRATEGIC_FIT = "strategic_fit"  # Focus on strategic alignment


class QueryType(Enum):
    """Query type based on available data."""
    STRUCTURED_ONLY = "structured_only"  # Only structured/financial data
    TEXT_ONLY = "text_only"  # Only text documents
    MULTI_MODAL = "multi_modal"  # Both structured and text data


class QueryPreprocessor:
    """
    Preprocessor for similarity search queries.
    
    This class handles:
    - Extracting metadata from query input
    - Parsing documents (PDFs) if provided
    - Identifying query context (screening, risk, exit, strategic)
    - Determining query type (Decision Point D2: routes to appropriate encoder)
    - Preparing deal objects for encoding
    
    According to the consolidated document:
    - Query Type Decision (D2) routes to:
      * Structured encoder only if query is structured
      * Text encoder only if query is text-only
      * Multi-modal encoder if both are available
    """
    
    # Context detection keywords
    CONTEXT_KEYWORDS: Dict[QueryContext, List[str]] = {
        QueryContext.SCREENING: [
            "screening", "initial review", "first pass", "financial profile",
            "growth profile", "similar metrics"
        ],
        QueryContext.RISK_ASSESSMENT: [
            "risk", "risks", "risk assessment", "concerns", "risk factors",
            "churn risk", "regulatory risk"
        ],
        QueryContext.EXIT_POTENTIAL: [
            "exit", "exit potential", "exit multiple", "exit valuation",
            "similar exits", "comparable exits"
        ],
        QueryContext.STRATEGIC_FIT: [
            "strategic", "strategic fit", "strategic alignment", "platform",
            "roll-up", "synergy"
        ]
    }
    
    def __init__(self):
        """Initialize query preprocessor."""
        self.pdf_extractor = PDFExtractor()
        logger.info("QueryPreprocessor initialized")
    
    def preprocess_query(
        self,
        deal: Optional[Deal] = None,
        metadata: Optional[Dict] = None,
        structured_data: Optional[Dict] = None,
        cim_text: Optional[str] = None,
        cim_pdf_path: Optional[str] = None,
        memo_text: Optional[str] = None,
        memo_pdf_path: Optional[str] = None,
        context: Optional[str] = None,
        user_query_text: Optional[str] = None
    ) -> Tuple[Deal, QueryType, QueryContext]:
        """
        Preprocess query input into a Deal object with identified context and type.
        
        Args:
            deal: Optional pre-constructed Deal object
            metadata: Optional metadata dictionary
            structured_data: Optional structured features dictionary
            cim_text: Optional CIM document text
            cim_pdf_path: Optional path to CIM PDF file
            memo_text: Optional investment memo text
            memo_pdf_path: Optional path to memo PDF file
            context: Optional explicit context (overrides detection)
            user_query_text: Optional user query text for context detection
            
        Returns:
            Tuple of (Deal object, QueryType, QueryContext)
            
        Raises:
            ValueError: If insufficient data provided to construct query
        """
        # Extract or construct deal
        if deal:
            query_deal = deal
        else:
            query_deal = self._construct_deal(
                metadata=metadata,
                structured_data=structured_data,
                cim_text=cim_text,
                cim_pdf_path=cim_pdf_path,
                memo_text=memo_text,
                memo_pdf_path=memo_pdf_path
            )
        
        # Determine query context
        query_context = self._identify_context(context, user_query_text, query_deal)
        
        # Determine query type (Decision Point D2)
        query_type = self._identify_query_type(query_deal)
        
        logger.info(
            f"Query preprocessed: type={query_type.value}, "
            f"context={query_context.value}, deal_id={query_deal.metadata.deal_id}"
        )
        
        return query_deal, query_type, query_context
    
    def _construct_deal(
        self,
        metadata: Optional[Dict] = None,
        structured_data: Optional[Dict] = None,
        cim_text: Optional[str] = None,
        cim_pdf_path: Optional[str] = None,
        memo_text: Optional[str] = None,
        memo_pdf_path: Optional[str] = None
    ) -> Deal:
        """
        Construct a Deal object from provided data.
        
        Args:
            metadata: Metadata dictionary
            structured_data: Structured features dictionary
            cim_text: CIM text
            cim_pdf_path: Path to CIM PDF
            memo_text: Memo text
            memo_pdf_path: Path to memo PDF
            
        Returns:
            Constructed Deal object
            
        Raises:
            ValueError: If insufficient data to construct deal
        """
        # Extract text from PDFs if paths provided
        if cim_pdf_path:
            try:
                cim_text = self.pdf_extractor.extract_cim_text(cim_pdf_path)
                logger.info(f"Extracted CIM text from {cim_pdf_path}")
            except Exception as e:
                logger.warning(f"Failed to extract CIM text from PDF: {e}")
        
        if memo_pdf_path:
            try:
                memo_text = self.pdf_extractor.extract_memo_text(memo_pdf_path)
                logger.info(f"Extracted memo text from {memo_pdf_path}")
            except Exception as e:
                logger.warning(f"Failed to extract memo text from PDF: {e}")
        
        # Construct metadata
        if metadata:
            deal_metadata = DealMetadata(**metadata)
        else:
            # Create default metadata
            deal_metadata = DealMetadata(
                deal_id="query_deal",
                company_name="Query Company",
                sector="Unknown",
                geography="US"
            )
        
        # Construct structured features
        if structured_data:
            deal_structured = StructuredFeatures(**structured_data)
        else:
            deal_structured = StructuredFeatures()
        
        # Construct text embeddings (will be populated by encoder)
        deal_text_embeddings = TextEmbeddings()
        
        # Store raw text for later encoding
        if cim_text:
            deal_text_embeddings.cim_overall = None  # Will be set by encoder
        if memo_text:
            deal_text_embeddings.ic_memo = None  # Will be set by encoder
        
        return Deal(
            metadata=deal_metadata,
            structured_features=deal_structured,
            text_embeddings=deal_text_embeddings
        )
    
    def _identify_context(
        self,
        explicit_context: Optional[str],
        user_query_text: Optional[str],
        deal: Deal
    ) -> QueryContext:
        """
        Identify query context from explicit input or implicit signals.
        
        Args:
            explicit_context: Explicitly provided context string
            user_query_text: User query text for context detection
            deal: Deal object (may contain context clues)
            
        Returns:
            Identified QueryContext
        """
        # If explicit context provided, use it
        if explicit_context:
            try:
                return QueryContext(explicit_context.lower())
            except ValueError:
                logger.warning(f"Unknown explicit context: {explicit_context}, using default")
                return QueryContext.DEFAULT
        
        # Detect context from user query text
        if user_query_text:
            text_lower = user_query_text.lower()
            
            # Score each context
            context_scores = {}
            for context, keywords in self.CONTEXT_KEYWORDS.items():
                score = sum(1 for keyword in keywords if keyword in text_lower)
                if score > 0:
                    context_scores[context] = score
            
            if context_scores:
                # Return context with highest score
                return max(context_scores.items(), key=lambda x: x[1])[0]
        
        # Default context
        return QueryContext.DEFAULT
    
    def _identify_query_type(self, deal: Deal) -> QueryType:
        """
        Identify query type based on available data (Decision Point D2).
        
        Routes to:
        - STRUCTURED_ONLY if only structured data available
        - TEXT_ONLY if only text data available
        - MULTI_MODAL if both available
        
        Args:
            deal: Deal object to analyze
            
        Returns:
            Identified QueryType
        """
        has_structured = False
        has_text = False
        
        # Check for structured data
        if deal.structured_features:
            features = deal.structured_features
            has_structured = any([
                features.revenue is not None,
                features.ebitda is not None,
                features.growth_rate is not None,
                features.enterprise_value is not None
            ])
        
        # Check for text data
        if deal.text_embeddings:
            has_text = deal.text_embeddings.get_primary_embedding() is not None
        
        # Determine type
        if has_structured and has_text:
            return QueryType.MULTI_MODAL
        elif has_structured:
            return QueryType.STRUCTURED_ONLY
        elif has_text:
            return QueryType.TEXT_ONLY
        else:
            # Default to structured if no data (will use default values)
            logger.warning("No data detected, defaulting to structured query")
            return QueryType.STRUCTURED_ONLY
    
    def extract_metadata(self, deal: Deal) -> Dict:
        """
        Extract metadata dictionary from deal.
        
        Args:
            deal: Deal object
            
        Returns:
            Metadata dictionary
        """
        return deal.metadata.to_dict()
    
    def get_context_weights(self, context: QueryContext) -> Dict[str, float]:
        """
        Get default weights for similarity computation based on context.
        
        According to the consolidated document:
        - Screening: w_struct=0.7, w_text=0.3
        - Risk Assessment: w_struct=0.2, w_text=0.7
        - Exit Potential: w_struct=0.5, w_text=0.5
        - Strategic Fit: w_struct=0.1, w_text=0.8
        
        Args:
            context: Query context
            
        Returns:
            Dictionary with weight values
        """
        weights_map = {
            QueryContext.DEFAULT: {"structured": 0.4, "text": 0.6, "metadata": 0.1},
            QueryContext.SCREENING: {"structured": 0.7, "text": 0.3, "metadata": 0.1},
            QueryContext.RISK_ASSESSMENT: {"structured": 0.2, "text": 0.7, "metadata": 0.1},
            QueryContext.EXIT_POTENTIAL: {"structured": 0.5, "text": 0.5, "metadata": 0.1},
            QueryContext.STRATEGIC_FIT: {"structured": 0.1, "text": 0.8, "metadata": 0.1}
        }
        
        return weights_map.get(context, weights_map[QueryContext.DEFAULT])

