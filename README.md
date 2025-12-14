# Deal Similarity System - MVP Implementation

A multi-modal similarity search system for finding similar historical deals to new CIM (Confidential Information Memorandum) opportunities in private equity and investment firms.RAG-based AI system for private equity deal similarity search. Analyzes Equity CIM documents using multi-modal embeddings (structured financial data + text) to find comparable historical deals in seconds.

## Project Structure

```
Conquer/
├── src/                          # Main source code
│   ├── ingestion/               # Data ingestion layer
│   │   ├── __init__.py
│   │   ├── crm_connector.py    # CRM data normalization
│   │   └── pdf_extractor.py    # PDF text extraction
│   ├── embedding/               # Embedding generation
│   │   ├── __init__.py
│   │   ├── structured_encoder.py  # Structured features encoding
│   │   ├── text_encoder.py       # Text embeddings
│   │   └── fusion.py             # Multi-modal fusion
│   ├── storage/                 # Data storage layer
│   │   ├── __init__.py
│   │   ├── vector_store.py      # Vector database (FAISS)
│   │   └── metadata_store.py    # Metadata storage
│   ├── retrieval/               # Retrieval and ranking
│   │   ├── __init__.py
│   │   ├── similarity.py        # Similarity scoring
│   │   └── ranker.py            # Result ranking
│   ├── models/                  # Data models
│   │   ├── __init__.py
│   │   └── deal.py              # Deal representation
│   └── utils/                   # Utilities
│       ├── __init__.py
│       └── config.py            # Configuration management
├── api/                         # FastAPI application
│   ├── __init__.py
│   ├── main.py                  # API endpoints
│   └── schemas.py               # API schemas
├── ui/                          # Streamlit UI
│   ├── __init__.py
│   └── app.py                   # Main UI application
├── config/                      # Configuration files
│   └── settings.yaml            # System settings
├── tests/                       # Unit tests
│   └── __init__.py
├── data/                        # Data storage
│   ├── crm/                     # CRM data samples
│   ├── documents/               # PDF documents
│   └── vectors/                 # Vector indices
├── requirements.txt             # Python dependencies
└── Documentation/               # Project documentation

```

## Quick Start

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Configure settings in `config/settings.yaml`

3. Run the API:
```bash
cd api && uvicorn main:app --reload
```

4. Run the UI:
```bash
streamlit run ui/app.py
```

## Architecture Overview

The system uses a modular microservices architecture with clear separation of concerns:
- **Ingestion**: Normalizes and extracts data from CRM and PDFs
- **Embedding**: Generates multi-modal representations
- **Storage**: Hybrid vector + metadata storage
- **Retrieval**: Similarity search and ranking
- **API/UI**: Interfaces for analyst interaction


