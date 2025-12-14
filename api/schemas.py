"""
API request/response schemas using Pydantic.

This module defines the data models for API endpoints.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class DealMetadataSchema(BaseModel):
    """Schema for deal metadata."""
    deal_id: str
    company_name: str
    sector: str
    subsector: Optional[str] = None
    geography: str = "US"
    deal_type: str = "Growth"
    deal_year: int = 2024
    deal_size: Optional[float] = None
    ownership_type: Optional[str] = None
    outcome: Optional[str] = None
    fund: Optional[str] = None


class StructuredFeaturesSchema(BaseModel):
    """Schema for structured features."""
    revenue: Optional[float] = None
    ebitda: Optional[float] = None
    growth_rate: Optional[float] = None
    margin: Optional[float] = None
    enterprise_value: Optional[float] = None
    leverage: Optional[float] = None
    free_cash_flow: Optional[float] = None


class DealCreateSchema(BaseModel):
    """Schema for creating a new deal."""
    metadata: DealMetadataSchema
    structured_features: StructuredFeaturesSchema
    cim_text: Optional[str] = None
    memo_text: Optional[str] = None
    notes_text: Optional[str] = None


class SimilarityBreakdownSchema(BaseModel):
    """Schema for similarity score breakdown."""
    structured: float
    text: float
    metadata: float
    overall: float


class SimilarDealSchema(BaseModel):
    """Schema for similar deal result."""
    deal_id: str
    company_name: str
    sector: str
    deal_type: str
    deal_year: int
    similarity_score: float
    breakdown: SimilarityBreakdownSchema
    metadata: Dict[str, Any] = {}


class SearchRequestSchema(BaseModel):
    """Schema for similarity search request."""
    deal_id: Optional[str] = None
    deal_data: Optional[DealCreateSchema] = None
    context: str = "default"
    top_k: int = Field(default=10, ge=1, le=50)
    similarity_threshold: Optional[float] = Field(default=None, ge=0.0, le=1.0)


class SearchResponseSchema(BaseModel):
    """Schema for similarity search response."""
    query_deal_id: Optional[str] = None
    context: str
    total_results: int
    similar_deals: List[SimilarDealSchema]


class HealthCheckSchema(BaseModel):
    """Schema for health check response."""
    status: str
    total_deals: int
    vector_store_size: int
    timestamp: datetime


