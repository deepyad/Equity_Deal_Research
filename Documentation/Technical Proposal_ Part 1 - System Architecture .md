<img src="https://r2cdn.perplexity.ai/pplx-full-logo-primary-dark%402x.png" style="height:64px;margin-right:32px"/>

# Technical Proposal: Part 1 - System Architecture (30%)

## Executive Summary

This section describes a scalable system architecture for surfacing similar historical deals to new CIM opportunities. The design centers on multi-modal deal representations combining structured CRM metrics with unstructured document embeddings, stored in a hybrid vector/metadata database for efficient similarity search. Analyst feedback enables continuous refinement of representations and search logic.

## 1.1 High-Level Architecture

```
[CRM + Document Repos] → [Ingestion Layer] → [Embedding Service] → [Vector + Metadata Store]
                                                                 ↓
[New CIM Input] → [Retrieval API] → [Analyst UI + Feedback] → [Tuning Loop]
```

**Key Components:**

- **Ingestion Layer**: Connectors normalize CRM data, OCR-parse CIM PDFs using LayoutLM for layout-aware extraction.
- **Embedding Service**: Generates composite deal representations from structured + unstructured data.
- **Vector Store**: Pinecone/FAISS for ANN similarity search + PostgreSQL for metadata filtering (sector, date, outcome).
- **Retrieval API**: Processes new deals, computes embeddings, retrieves top-k matches.
- **UI Layer**: Workflow-integrated interface showing similar deals with explainability.


## 1.2 Deal Representation Strategy

Deals represented as **structured schema + multi-vector embedding**:

```
Deal ID: "cloudsecure-2025"
├── Metadata: {sector: "Software", geography: "US", deal_type: "Growth", year: 2025}
├── Structured Features: [log_rev=3.4, growth_z=0.9, margin_z=0.7, ...] (128-dim)
├── Text Embeddings:
│   ├── cim_overall: [0.12, -0.45, ...] (1024-dim)
│   ├── business_section: [...]
│   └── ic_memo: [...]
└── Qualitative Tags: ["high_churn_risk", "usage_pricing"]
```

**Enables similarity comparison** via cosine distance on joint embeddings or separate modality scores.

## 1.3 Embedding Strategies

### Structured Metrics

```
x_struct = [normalized_financials] + [sector_embeddings] + [temporal_features]
```

- **Financials**: Log-transform revenues/EBITDA, z-score growth/margins per sector/year.
- **Categorical**: Learned embeddings for sectors (healthcare IT ≈ SaaS), deal types.
- **Temporal**: Deal year + macro regime flags (low/high rates).


### Unstructured Documents

- **Extraction**: Layout-aware PDF parsing preserves tables/headings context.
- **Encoding**: FinBERT/sentence-transformers, section-level granularity.
- **Investment Memos/Notes**: Higher weight due to decision rationale capture.


### Multi-Modal Fusion

```
Joint: FFN(concat(x_struct, x_text))  // Contrastive training
OR
Late: s_final = w_struct * s_struct + w_text * s_text  // w=0.4/0.6 initial
```

**Handles multi-modality** by aligning representations in shared space, supporting queries like "similar growth in adjacent sectors" via weighted retrieval.

***

