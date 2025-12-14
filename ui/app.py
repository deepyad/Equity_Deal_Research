"""
Streamlit UI application for Deal Similarity System.

This module provides a web-based interface for analysts to:
- Search for similar deals
- View similarity results with explanations
- Adjust similarity context and weights
- Provide feedback on results
"""

import streamlit as st
import sys
from pathlib import Path
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.deal import Deal, DealMetadata, StructuredFeatures
from src.ingestion.crm_connector import CRMConnector
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

# Page configuration
st.set_page_config(
    page_title="Deal Similarity System",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Load configuration
@st.cache_resource
def load_system_components():
    """Load and cache system components."""
    config = load_config()
    return {
        "config": config,
        "pdf_extractor": PDFExtractor(),
        "structured_encoder": StructuredEncoder(),
        "text_encoder": TextEncoder(),
        "vector_store": VectorStore(),
        "metadata_store": MetadataStore(),
        "similarity_calculator": SimilarityCalculator(),
        "ranker": ResultRanker()
    }

# Initialize components
components = load_system_components()
pdf_extractor = components["pdf_extractor"]
structured_encoder = components["structured_encoder"]
text_encoder = components["text_encoder"]
vector_store = components["vector_store"]
metadata_store = components["metadata_store"]
similarity_calculator = components["similarity_calculator"]
ranker = components["ranker"]
config = components["config"]

# Sidebar
with st.sidebar:
    st.title("🔍 Deal Similarity System")
    st.markdown("---")
    
    # Similarity context selection
    st.subheader("Similarity Context")
    context = st.selectbox(
        "Select search context",
        ["default", "screening", "risk_assessment", "exit_potential", "strategic_fit"],
        help="Different contexts weight structured vs text features differently"
    )
    
    # Similarity threshold
    st.subheader("Filters")
    similarity_threshold = st.slider(
        "Minimum similarity score",
        min_value=0.0,
        max_value=1.0,
        value=0.6,
        step=0.05,
        help="Only show deals above this similarity threshold"
    )
    
    # Number of results
    top_k = st.slider(
        "Number of results",
        min_value=5,
        max_value=50,
        value=10,
        step=5
    )
    
    st.markdown("---")
    
    # System stats
    st.subheader("System Status")
    total_deals = metadata_store.get_total_deals()
    st.metric("Total Deals", total_deals)
    st.metric("Vector Store Size", vector_store.get_total_deals())

# Main content
st.title("🔍 Deal Similarity Search")
st.markdown("Find similar historical deals to new CIM opportunities")

# Tabs
tab1, tab2, tab3 = st.tabs(["Search", "Add Deal", "Browse Deals"])

with tab1:
    st.header("Search for Similar Deals")
    
    # Input method selection
    input_method = st.radio(
        "Input method",
        ["Enter Deal Details", "Upload CRM Data", "Load Existing Deal"],
        horizontal=True
    )
    
    query_deal = None
    
    if input_method == "Enter Deal Details":
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Company Information")
            company_name = st.text_input("Company Name", value="Example Corp")
            sector = st.selectbox(
                "Sector",
                ["Software", "Healthcare IT", "Financial Technology", 
                 "E-commerce", "Business Services", "Manufacturing"]
            )
            geography = st.text_input("Geography", value="US")
            deal_type = st.selectbox(
                "Deal Type",
                ["Growth", "Buyout", "Minority", "Majority"]
            )
            deal_year = st.number_input("Deal Year", min_value=2010, max_value=2030, value=2024)
        
        with col2:
            st.subheader("Financial Metrics")
            revenue = st.number_input("Revenue (USD)", min_value=0.0, value=10000000.0)
            ebitda = st.number_input("EBITDA (USD)", min_value=None, value=2000000.0)
            growth_rate = st.number_input("Growth Rate (decimal)", min_value=-1.0, max_value=2.0, value=0.25, step=0.05)
            margin = st.number_input("EBITDA Margin (decimal)", min_value=-1.0, max_value=1.0, value=0.2, step=0.05)
            enterprise_value = st.number_input("Enterprise Value (USD)", min_value=0.0, value=None)
        
        st.subheader("Document Content (Optional)")
        cim_text = st.text_area("CIM Text Content", height=200, help="Paste CIM document text here")
        memo_text = st.text_area("Investment Memo Text", height=150, help="Paste investment memo text here")
        
        if st.button("Search Similar Deals", type="primary"):
            # Create query deal
            metadata = DealMetadata(
                deal_id=f"query-{datetime.now().timestamp()}",
                company_name=company_name,
                sector=sector,
                geography=geography,
                deal_type=deal_type,
                deal_year=deal_year
            )
            
            structured = StructuredFeatures(
                revenue=revenue,
                ebitda=ebitda,
                growth_rate=growth_rate,
                margin=margin,
                enterprise_value=enterprise_value
            )
            
            query_deal = Deal(
                metadata=metadata,
                structured_features=structured,
                text_embeddings=text_encoder.text_embeddings if hasattr(text_encoder, 'text_embeddings') else None
            )
    
    elif input_method == "Upload CRM Data":
        uploaded_file = st.file_uploader("Upload CRM Data (CSV or JSON)", type=["csv", "json"])
        if uploaded_file:
            # Process uploaded file
            st.info("CRM upload functionality - to be implemented")
    
    elif input_method == "Load Existing Deal":
        deal_id = st.text_input("Deal ID")
        if st.button("Load Deal"):
            deal_dict = metadata_store.get_deal(deal_id)
            if deal_dict:
                st.success(f"Loaded deal: {deal_dict['company_name']}")
                # Use deal_dict to create query_deal
            else:
                st.error(f"Deal {deal_id} not found")
    
    # Display results
    if query_deal:
        with st.spinner("Searching for similar deals..."):
            try:
                # Generate embeddings
                struct_vector = structured_encoder.transform(query_deal)
                
                if cim_text or memo_text:
                    text_embeddings = text_encoder.encode_deal_documents(
                        query_deal,
                        cim_text=cim_text if 'cim_text' in locals() else None,
                        memo_text=memo_text if 'memo_text' in locals() else None
                    )
                    query_deal.text_embeddings = text_embeddings
                
                primary_text_emb = query_deal.text_embeddings.get_primary_embedding() if query_deal.text_embeddings else None
                query_embedding = primary_text_emb if primary_text_emb is not None else struct_vector
                
                # Set context
                similarity_calculator.set_context(context)
                
                # Search
                vector_results = vector_store.search(query_embedding, top_k=top_k * 2)
                
                if vector_results:
                    # Load candidate deals
                    candidate_ids = [deal_id for deal_id, _ in vector_results]
                    candidate_dicts = metadata_store.get_deals_by_ids(candidate_ids)
                    
                    # Display results
                    st.subheader(f"Found {len(candidate_dicts)} Similar Deals")
                    
                    for i, deal_dict in enumerate(candidate_dicts[:top_k], 1):
                        with st.expander(
                            f"#{i}: {deal_dict['company_name']} - "
                            f"{deal_dict.get('sector', 'Unknown')} - "
                            f"Year: {deal_dict.get('deal_year', 'N/A')}"
                        ):
                            col1, col2, col3 = st.columns(3)
                            
                            with col1:
                                st.metric("Deal ID", deal_dict['deal_id'])
                                st.metric("Sector", deal_dict.get('sector', 'N/A'))
                                st.metric("Geography", deal_dict.get('geography', 'N/A'))
                            
                            with col2:
                                st.metric("Deal Type", deal_dict.get('deal_type', 'N/A'))
                                st.metric("Revenue", f"${deal_dict.get('revenue', 0):,.0f}" if deal_dict.get('revenue') else 'N/A')
                                st.metric("Growth Rate", f"{deal_dict.get('growth_rate', 0)*100:.1f}%" if deal_dict.get('growth_rate') else 'N/A')
                            
                            with col3:
                                st.metric("Deal Year", deal_dict.get('deal_year', 'N/A'))
                                st.metric("Outcome", deal_dict.get('outcome', 'N/A'))
                            
                            # Feedback buttons
                            col_fb1, col_fb2, col_fb3 = st.columns(3)
                            with col_fb1:
                                st.button("👍 Useful", key=f"useful_{i}")
                            with col_fb2:
                                st.button("👎 Not Useful", key=f"not_useful_{i}")
                            with col_fb3:
                                st.button("⭐ Save", key=f"save_{i}")
                else:
                    st.warning("No similar deals found. Try adjusting your search criteria.")
            
            except Exception as e:
                st.error(f"Error during search: {str(e)}")
                logger.error(f"Search error: {e}")

with tab2:
    st.header("Add New Deal to System")
    st.info("Add historical deals to build the similarity database")
    
    # Form for adding deals
    with st.form("add_deal_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            deal_id = st.text_input("Deal ID *", value=f"deal-{datetime.now().timestamp()}")
            company_name = st.text_input("Company Name *")
            sector = st.selectbox("Sector", ["Software", "Healthcare IT", "Financial Technology", 
                                           "E-commerce", "Business Services", "Manufacturing"])
            geography = st.text_input("Geography", value="US")
            deal_type = st.selectbox("Deal Type", ["Growth", "Buyout", "Minority", "Majority"])
            deal_year = st.number_input("Deal Year", min_value=2010, max_value=2030, value=2024)
        
        with col2:
            revenue = st.number_input("Revenue (USD)", min_value=0.0, value=0.0)
            ebitda = st.number_input("EBITDA (USD)", min_value=None, value=None)
            growth_rate = st.number_input("Growth Rate", min_value=-1.0, max_value=2.0, value=0.0, step=0.05)
            margin = st.number_input("EBITDA Margin", min_value=-1.0, max_value=1.0, value=0.0, step=0.05)
        
        cim_file = st.file_uploader("Upload CIM PDF (Optional)", type=["pdf"])
        
        submitted = st.form_submit_button("Add Deal", type="primary")
        
        if submitted:
            if company_name:
                try:
                    # Create deal
                    metadata = DealMetadata(
                        deal_id=deal_id,
                        company_name=company_name,
                        sector=sector,
                        geography=geography,
                        deal_type=deal_type,
                        deal_year=deal_year
                    )
                    
                    structured = StructuredFeatures(
                        revenue=revenue if revenue > 0 else None,
                        ebitda=ebitda,
                        growth_rate=growth_rate if growth_rate != 0 else None,
                        margin=margin if margin != 0 else None
                    )
                    
                    deal = Deal(metadata=metadata, structured_features=structured)
                    
                    # Extract PDF if provided
                    cim_text = None
                    if cim_file:
                        # Save temporarily and extract
                        temp_path = Path(f"/tmp/{cim_file.name}")
                        with open(temp_path, "wb") as f:
                            f.write(cim_file.getbuffer())
                        cim_text = pdf_extractor.extract_text(str(temp_path))
                        temp_path.unlink()
                    
                    # Generate embeddings
                    struct_vector = structured_encoder.transform(deal)
                    
                    if cim_text:
                        text_embeddings = text_encoder.encode_deal_documents(deal, cim_text=cim_text)
                        deal.text_embeddings = text_embeddings
                    
                    primary_text_emb = deal.text_embeddings.get_primary_embedding() if deal.text_embeddings else None
                    primary_embedding = primary_text_emb if primary_text_emb else struct_vector
                    
                    # Add to stores
                    vector_store.add_deal(deal, primary_embedding)
                    metadata_store.add_deal(deal)
                    vector_store.save()
                    
                    st.success(f"Deal '{company_name}' added successfully!")
                    st.balloons()
                
                except Exception as e:
                    st.error(f"Error adding deal: {str(e)}")
            else:
                st.error("Please provide a company name")

with tab3:
    st.header("Browse All Deals")
    
    # Filters
    col1, col2, col3 = st.columns(3)
    with col1:
        filter_sector = st.selectbox("Filter by Sector", ["All"] + ["Software", "Healthcare IT", 
                                                                    "Financial Technology", 
                                                                    "E-commerce", "Business Services"])
    with col2:
        filter_deal_type = st.selectbox("Filter by Deal Type", ["All", "Growth", "Buyout", "Minority", "Majority"])
    with col3:
        filter_year = st.selectbox("Filter by Year", ["All"] + [str(y) for y in range(2024, 2010, -1)])
    
    # Get deals
    filters = {}
    if filter_sector != "All":
        filters["sector"] = filter_sector
    if filter_deal_type != "All":
        filters["deal_type"] = filter_deal_type
    if filter_year != "All":
        filters["min_year"] = int(filter_year)
        filters["max_year"] = int(filter_year)
    
    deals = metadata_store.search_deals(filters=filters, limit=100)
    
    st.subheader(f"Showing {len(deals)} Deals")
    
    for deal_dict in deals:
        with st.expander(f"{deal_dict['company_name']} - {deal_dict.get('sector', 'N/A')}"):
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**Deal ID:** {deal_dict['deal_id']}")
                st.write(f"**Sector:** {deal_dict.get('sector', 'N/A')}")
                st.write(f"**Geography:** {deal_dict.get('geography', 'N/A')}")
                st.write(f"**Deal Type:** {deal_dict.get('deal_type', 'N/A')}")
            with col2:
                st.write(f"**Year:** {deal_dict.get('deal_year', 'N/A')}")
                st.write(f"**Revenue:** ${deal_dict.get('revenue', 0):,.0f}" if deal_dict.get('revenue') else "**Revenue:** N/A")
                st.write(f"**Growth Rate:** {deal_dict.get('growth_rate', 0)*100:.1f}%" if deal_dict.get('growth_rate') else "**Growth Rate:** N/A")
                st.write(f"**Outcome:** {deal_dict.get('outcome', 'N/A')}")

if __name__ == "__main__":
    # Streamlit runs automatically
    pass


