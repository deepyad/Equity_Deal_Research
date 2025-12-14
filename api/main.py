"""
FastAPI main application.

This module defines the REST API endpoints for the Deal Similarity System.
"""

import logging
from datetime import datetime
from typing import List, Optional
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from api.schemas import (
    DealCreateSchema, SearchRequestSchema, SearchResponseSchema,
    SimilarDealSchema, SimilarityBreakdownSchema, HealthCheckSchema
)
from src.models.deal import Deal, DealMetadata, StructuredFeatures, TextEmbeddings
from src.ingestion.pdf_extractor import PDFExtractor
from src.embedding.structured_encoder import StructuredEncoder
from src.embedding.text_encoder import TextEncoder
from src.storage.vector_store import VectorStore
from src.storage.metadata_store import MetadataStore
from src.retrieval.similarity import SimilarityCalculator
from src.retrieval.ranker import ResultRanker
from src.utils.config import load_config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load configuration
config = load_config()

# Initialize FastAPI app
app = FastAPI(
    title="Deal Similarity API",
    description="API for finding similar historical deals to new CIM opportunities",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize components
pdf_extractor = PDFExtractor()
structured_encoder = StructuredEncoder()
text_encoder = TextEncoder()
vector_store = VectorStore()
metadata_store = MetadataStore()
similarity_calculator = SimilarityCalculator()
ranker = ResultRanker()


@app.on_event("startup")
async def startup_event():
    """Initialize components on startup."""
    logger.info("Starting Deal Similarity API...")
    logger.info(f"Vector store contains {vector_store.get_total_deals()} deals")
    logger.info(f"Metadata store contains {metadata_store.get_total_deals()} deals")


@app.get("/health", response_model=HealthCheckSchema)
async def health_check():
    """
    Health check endpoint.
    
    Returns system status and basic statistics.
    """
    return HealthCheckSchema(
        status="healthy",
        total_deals=metadata_store.get_total_deals(),
        vector_store_size=vector_store.get_total_deals(),
        timestamp=datetime.now()
    )


@app.post("/deals", status_code=status.HTTP_201_CREATED)
async def create_deal(deal_data: DealCreateSchema):
    """
    Create a new deal in the system.
    
    This endpoint:
    1. Processes the deal data
    2. Generates embeddings
    3. Stores in vector and metadata stores
    """
    try:
        # Convert schema to Deal object
        metadata = DealMetadata(**deal_data.metadata.dict())
        structured = StructuredFeatures(**deal_data.structured_features.dict())
        text_embeddings = TextEmbeddings()
        
        deal = Deal(
            metadata=metadata,
            structured_features=structured,
            text_embeddings=text_embeddings
        )
        
        # Generate embeddings
        # Structured features
        struct_vector = structured_encoder.transform(deal)
        
        # Text embeddings
        if deal_data.cim_text or deal_data.memo_text or deal_data.notes_text:
            text_embeddings = text_encoder.encode_deal_documents(
                deal,
                cim_text=deal_data.cim_text,
                memo_text=deal_data.memo_text,
                notes_text=deal_data.notes_text
            )
            deal.text_embeddings = text_embeddings
        
        # Get primary text embedding
        primary_text_emb = text_embeddings.get_primary_embedding()
        
        # For now, use text embedding as primary (can be fused later)
        primary_embedding = primary_text_emb if primary_text_emb else struct_vector
        
        # Add to stores
        vector_store.add_deal(deal, primary_embedding)
        metadata_store.add_deal(deal)
        
        # Save vector store
        vector_store.save()
        
        return {
            "deal_id": deal.metadata.deal_id,
            "status": "created",
            "message": "Deal successfully added to system"
        }
    
    except Exception as e:
        logger.error(f"Error creating deal: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create deal: {str(e)}"
        )


@app.post("/search", response_model=SearchResponseSchema)
async def search_similar_deals(request: SearchRequestSchema):
    """
    Search for similar deals.
    
    This endpoint:
    1. Loads or processes the query deal
    2. Searches for similar deals in the vector store
    3. Computes detailed similarity scores
    4. Ranks and returns results
    """
    try:
        # Load or create query deal
        if request.deal_id:
            # Load existing deal
            deal_dict = metadata_store.get_deal(request.deal_id)
            if not deal_dict:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Deal {request.deal_id} not found"
                )
            # Convert dict to Deal object (simplified - would need full conversion)
            # For now, we'll use deal_data if provided
            if not request.deal_data:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Must provide deal_data for similarity search"
                )
        
        if not request.deal_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Must provide either deal_id or deal_data"
            )
        
        # Create query deal
        metadata = DealMetadata(**request.deal_data.metadata.dict())
        structured = StructuredFeatures(**request.deal_data.structured_features.dict())
        text_embeddings = TextEmbeddings()
        
        query_deal = Deal(
            metadata=metadata,
            structured_features=structured,
            text_embeddings=text_embeddings
        )
        
        # Generate embeddings for query
        struct_vector = structured_encoder.transform(query_deal)
        
        if request.deal_data.cim_text or request.deal_data.memo_text:
            text_embeddings = text_encoder.encode_deal_documents(
                query_deal,
                cim_text=request.deal_data.cim_text,
                memo_text=request.deal_data.memo_text,
                notes_text=request.deal_data.notes_text
            )
            query_deal.text_embeddings = text_embeddings
        
        primary_text_emb = text_embeddings.get_primary_embedding()
        query_embedding = primary_text_emb if primary_text_emb else struct_vector
        
        # Set similarity context
        similarity_calculator.set_context(request.context)
        
        # Search in vector store
        vector_results = vector_store.search(
            query_embedding,
            top_k=min(request.top_k * 2, 50)  # Get more for re-ranking
        )
        
        if not vector_results:
            return SearchResponseSchema(
                query_deal_id=query_deal.metadata.deal_id,
                context=request.context,
                total_results=0,
                similar_deals=[]
            )
        
        # Load candidate deals from metadata store
        candidate_ids = [deal_id for deal_id, _ in vector_results]
        candidate_dicts = metadata_store.get_deals_by_ids(candidate_ids)
        
        # Convert to Deal objects and calculate detailed similarities
        similar_deals_list = []
        
        for deal_dict in candidate_dicts:
            # Reconstruct Deal object (simplified)
            # In production, would need proper deserialization
            candidate_metadata = DealMetadata(
                deal_id=deal_dict["deal_id"],
                company_name=deal_dict["company_name"],
                sector=deal_dict.get("sector", ""),
                subsector=deal_dict.get("subsector"),
                geography=deal_dict.get("geography", "US"),
                deal_type=deal_dict.get("deal_type", "Growth"),
                deal_year=deal_dict.get("deal_year", 2024),
                deal_size=deal_dict.get("deal_size"),
                ownership_type=deal_dict.get("ownership_type"),
                outcome=deal_dict.get("outcome"),
                fund=deal_dict.get("fund")
            )
            
            candidate_structured = StructuredFeatures(
                revenue=deal_dict.get("revenue"),
                ebitda=deal_dict.get("ebitda"),
                growth_rate=deal_dict.get("growth_rate"),
                margin=deal_dict.get("margin"),
                enterprise_value=deal_dict.get("enterprise_value"),
                leverage=deal_dict.get("leverage"),
                free_cash_flow=deal_dict.get("free_cash_flow")
            )
            
            # For now, use simple similarity from vector distance
            vector_distance = next((d for did, d in vector_results if did == deal_dict["deal_id"]), 1.0)
            similarity_score = max(0.0, 1.0 - vector_distance / 10.0)  # Rough conversion
            
            similar_deals_list.append(SimilarDealSchema(
                deal_id=deal_dict["deal_id"],
                company_name=deal_dict["company_name"],
                sector=deal_dict.get("sector", ""),
                deal_type=deal_dict.get("deal_type", ""),
                deal_year=deal_dict.get("deal_year", 2024),
                similarity_score=similarity_score,
                breakdown=SimilarityBreakdownSchema(
                    structured=similarity_score * 0.4,
                    text=similarity_score * 0.6,
                    metadata=0.0,
                    overall=similarity_score
                ),
                metadata=deal_dict
            ))
        
        # Sort by similarity score
        similar_deals_list.sort(key=lambda x: x.similarity_score, reverse=True)
        similar_deals_list = similar_deals_list[:request.top_k]
        
        return SearchResponseSchema(
            query_deal_id=query_deal.metadata.deal_id,
            context=request.context,
            total_results=len(similar_deals_list),
            similar_deals=similar_deals_list
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error searching similar deals: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Search failed: {str(e)}"
        )


@app.get("/deals/{deal_id}")
async def get_deal(deal_id: str):
    """
    Get deal details by ID.
    
    Args:
        deal_id: Deal identifier
        
    Returns:
        Deal information
    """
    deal_dict = metadata_store.get_deal(deal_id)
    if not deal_dict:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Deal {deal_id} not found"
        )
    return deal_dict


if __name__ == "__main__":
    import uvicorn
    api_config = config.get("api", {})
    uvicorn.run(
        "main:app",
        host=api_config.get("host", "0.0.0.0"),
        port=api_config.get("port", 8000),
        reload=api_config.get("reload", True)
    )


