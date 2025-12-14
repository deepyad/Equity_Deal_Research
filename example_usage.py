"""
Example usage script for Deal Similarity System.

This script demonstrates how to:
1. Load deals from CRM data
2. Extract text from PDFs
3. Generate embeddings
4. Store deals in the system
5. Search for similar deals
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.models.deal import Deal, DealMetadata, StructuredFeatures
from src.ingestion.crm_connector import CRMConnector
from src.ingestion.pdf_extractor import PDFExtractor
from src.embedding.structured_encoder import StructuredEncoder
from src.embedding.text_encoder import TextEncoder
from src.storage.vector_store import VectorStore
from src.storage.metadata_store import MetadataStore
from src.retrieval.similarity import SimilarityCalculator
from src.utils.config import load_config


def example_load_and_store_deals():
    """Example: Load deals from CRM and store them."""
    print("=" * 60)
    print("Example 1: Loading and Storing Deals")
    print("=" * 60)
    
    # Initialize components
    crm_connector = CRMConnector()
    pdf_extractor = PDFExtractor()
    structured_encoder = StructuredEncoder()
    text_encoder = TextEncoder()
    vector_store = VectorStore()
    metadata_store = MetadataStore()
    
    # Load deals from JSON file
    sample_data_path = "data/crm/sample_deals.json"
    
    if not Path(sample_data_path).exists():
        print(f"Sample data file not found: {sample_data_path}")
        print("Please ensure sample data exists in data/crm/")
        return
    
    deals = crm_connector.load_all_deals(sample_data_path)
    print(f"Loaded {len(deals)} deals from CRM data")
    
    # Process and store each deal
    for deal in deals:
        print(f"\nProcessing deal: {deal.metadata.company_name}")
        
        # Generate structured embeddings
        struct_vector = structured_encoder.transform(deal)
        
        # For demo purposes, use simple text
        demo_text = f"Company: {deal.metadata.company_name}. "
        demo_text += f"Sector: {deal.metadata.sector}. "
        demo_text += f"Revenue: ${deal.structured_features.revenue:,.0f} if deal.structured_features.revenue else 'N/A'}. "
        demo_text += f"Growth rate: {deal.structured_features.growth_rate*100:.1f}% if deal.structured_features.growth_rate else 'N/A'}."
        
        # Generate text embeddings
        text_embeddings = text_encoder.encode_deal_documents(deal, cim_text=demo_text)
        deal.text_embeddings = text_embeddings
        
        # Get primary embedding (combine structured + text)
        primary_text_emb = text_embeddings.get_primary_embedding()
        
        # Use text embedding as primary (in production, would fuse)
        primary_embedding = primary_text_emb if primary_text_emb else struct_vector
        
        # Store in vector and metadata stores
        vector_store.add_deal(deal, primary_embedding)
        metadata_store.add_deal(deal)
        
        print(f"  ✓ Stored in vector store and metadata store")
    
    # Save vector store
    vector_store.save()
    print(f"\n✓ Saved vector store with {vector_store.get_total_deals()} deals")
    print(f"✓ Metadata store contains {metadata_store.get_total_deals()} deals")


def example_search_similar_deals():
    """Example: Search for similar deals."""
    print("\n" + "=" * 60)
    print("Example 2: Searching for Similar Deals")
    print("=" * 60)
    
    # Initialize components
    structured_encoder = StructuredEncoder()
    text_encoder = TextEncoder()
    vector_store = VectorStore()
    metadata_store = MetadataStore()
    similarity_calculator = SimilarityCalculator(context="default")
    
    # Create a query deal
    query_metadata = DealMetadata(
        deal_id="query-001",
        company_name="SecureCloud Platform",
        sector="Software",
        geography="US",
        deal_type="Growth",
        deal_year=2024
    )
    
    query_structured = StructuredFeatures(
        revenue=18000000,
        ebitda=3600000,
        growth_rate=0.32,
        margin=0.20
    )
    
    query_deal = Deal(
        metadata=query_metadata,
        structured_features=query_structured
    )
    
    # Generate embeddings for query
    struct_vector = structured_encoder.transform(query_deal)
    
    query_text = "SecureCloud Platform is a B2B SaaS company providing cloud security solutions. "
    query_text += "The company serves mid-market enterprises with subscription-based pricing. "
    query_text += "Strong growth trajectory with 32% CAGR. Focus on recurring revenue model."
    
    text_embeddings = text_encoder.encode_deal_documents(query_deal, cim_text=query_text)
    query_deal.text_embeddings = text_embeddings
    
    primary_text_emb = text_embeddings.get_primary_embedding()
    query_embedding = primary_text_emb if primary_text_emb else struct_vector
    
    print(f"\nQuery Deal: {query_deal.metadata.company_name}")
    print(f"  Sector: {query_deal.metadata.sector}")
    print(f"  Revenue: ${query_deal.structured_features.revenue:,.0f}")
    print(f"  Growth Rate: {query_deal.structured_features.growth_rate*100:.1f}%")
    
    # Search for similar deals
    print("\nSearching for similar deals...")
    vector_results = vector_store.search(query_embedding, top_k=5)
    
    if not vector_results:
        print("No similar deals found. Please load some deals first.")
        return
    
    # Load candidate deals
    candidate_ids = [deal_id for deal_id, _ in vector_results]
    candidate_dicts = metadata_store.get_deals_by_ids(candidate_ids)
    
    print(f"\nFound {len(candidate_dicts)} similar deals:\n")
    
    for i, (deal_id, distance) in enumerate(vector_results[:5], 1):
        # Find matching deal dict
        deal_dict = next((d for d in candidate_dicts if d["deal_id"] == deal_id), None)
        
        if deal_dict:
            # Rough similarity score (1 - normalized distance)
            similarity_score = max(0.0, 1.0 - distance / 10.0)
            
            print(f"{i}. {deal_dict['company_name']}")
            print(f"   Deal ID: {deal_dict['deal_id']}")
            print(f"   Sector: {deal_dict.get('sector', 'N/A')}")
            print(f"   Revenue: ${deal_dict.get('revenue', 0):,.0f}" if deal_dict.get('revenue') else "   Revenue: N/A")
            print(f"   Similarity Score: {similarity_score:.2%}")
            print()


def main():
    """Run all examples."""
    print("\n" + "=" * 60)
    print("Deal Similarity System - Example Usage")
    print("=" * 60)
    
    # Load configuration
    load_config()
    
    # Run examples
    try:
        example_load_and_store_deals()
        example_search_similar_deals()
        
        print("\n" + "=" * 60)
        print("Examples completed successfully!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\nError running examples: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()


