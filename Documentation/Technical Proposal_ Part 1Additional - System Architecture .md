
## Overall system shape

The system would be built as a set of services around a "deal similarity" core:

- **Ingestion layer**: connectors to the CRM and document repositories that continuously pull new / updated deals, normalize fields (currencies, date formats, sector taxonomies), and run PDF OCR where needed.
- **Feature \& embedding service**: for each deal, this service extracts structured features, parses text from CIMs and memos, runs embedding models, and produces a standardized multi-modal representation object that can be versioned.
- **Vector + metadata store**: a vector database (for embeddings) coupled with a relational or document store (for raw features, IDs, and labels like outcome, fund, geography). The vector store supports approximate nearest-neighbor search; the metadata store supports filters (e.g., "only buyout deals post‑2018").
- **Retrieval \& ranking API**: given a new deal, it generates its representation, runs similarity search, then applies re-ranking logic (e.g., weighting by recency, sector match, or analyst feedback) before returning results.
- **Analyst UI + feedback**: a web app inside the firm's workflow that shows similar deals, surfaces key comparison attributes, and lets analysts mark deals as useful/not useful, pin favorites, or adjust weights (e.g., "care more about growth rate").
- **Offline training / tuning loop**: jobs that periodically retrain weights for combining modalities, update normalization parameters, and evaluate retrieval quality using historical data and feedback logs.

This separation lets you iterate on models and similarity logic without touching CRM integrations or the UI.

## Representing deals in detail

Each deal would be represented as a **structured schema plus one or more vectors**:

- **Core metadata**: ID, company name, date, geography, sector/subsector (normalized taxonomy), deal type (buyout, growth, minority, etc.), sponsor vs founder‑owned, and outcome (invested, passed, lost).
- **Financial feature block**: time-normalized metrics such as:
    - Size: revenue, EBITDA, enterprise value, deal size.
    - Profitability: margins, capex intensity, FCF margins.
    - Growth: 1‑, 3‑, 5‑year CAGR where available.
    - Capital structure: leverage, interest coverage, etc.
- **Qualitative tags**: patterns derived from text, such as "roll‑up platform," "software with usage‑based pricing," "regulated market," "customer concentration," "contracted revenue," etc.
- **Document embeddings**: vector representations for:
    - CIM overall.
    - Key sections (business overview, market, competition, financials).
    - Investment committee memo, first‑visit notes.

Internally, one can think of a deal as:

- A **structured feature vector** $x^{struct}$ (dozens to a few hundred numbers).
- A **text embedding vector** $x^{text}$ (e.g., 768–4096 dimensions).
- Optional **section‑level vectors** for finer-grained retrieval (e.g., one vector per CIM section).

The system can then compute similarity using these components either separately (e.g., "similar documents but not necessarily similar size") or in a fused way ("overall deal similarity").

## Embedding and representation strategies

### Structured metrics

For structured data, the goal is to make distances meaningful:

- **Normalization and scaling**: convert monetary values to a common currency and scale with log transforms or z‑scores so a tenfold revenue difference is treated reasonably. Growth rates and margins are already bounded and can be standardized per sector.
- **Categorical encoding**:
    - Sectors, subsectors, regions as learned embeddings (not just one-hot), so similar sectors (e.g., healthcare IT and general SaaS) are closer than unrelated ones (e.g., SaaS vs mining).
    - Deal type, ownership type, and stage also get embeddings.
- **Temporal features**: include deal year, "pre‑COVID / COVID / post‑COVID" flags, and macro tags (e.g., low‑rate vs high‑rate environment), so similarity reflects changing market regimes.

A simple starting representation is just a concatenated vector of normalized numeric features and dense categorical embeddings. Later, this can feed a small neural encoder or autoencoder to learn a compressed embedding that places "economically similar" deals closer together.

### Text and document embeddings

For unstructured content, the goals are to capture:

- Business model specifics (pricing, customer type, go‑to‑market).
- Market context and competitive dynamics.
- Qualitative risk/reward drivers (e.g., regulatory risk, customer concentration, key-person risk).

Concretely:

- **Text extraction**: for CIMs and memos, use a layout-aware PDF parser so that tables, headings, and bullets are parsed sensibly; this avoids losing important context like which numbers are historical vs projected.
- **Base models**: start with a strong sentence/document embedding model (e.g., a modern sentence-transformer tuned for semantic similarity). For financial language, consider a domain-tuned version, or further fine-tune on the firm's own corpus using contrastive learning (e.g., pull together sections from the same deal, push apart unrelated deals).
- **Section-level embeddings**: compute embeddings at section granularity (e.g., one vector for "business overview," one for "market," one for "financial highlights"). This supports targeted queries like "show deals with similar market dynamics even if the financial profile differs."
- **IC memo / notes embeddings**: treat investment memos and analyst notes as especially important signals, often closer to how the firm actually reasons ("strong product, but high churn; concerns on management depth"). These can get extra weight in similarity scoring.

### Fusion strategies

There are a few pragmatic ways to fuse structured and text representations:

- **Simple concatenation + projection**: concatenate $x^{struct}$ and $x^{text}$ and pass them through a small feed-forward network to obtain a joint embedding used for similarity. This can be trained using historical labels (e.g., deals evaluated by the same team, or deals that analysts manually mark as "similar").
- **Late fusion / weighted similarity**: compute a structured similarity score $s_{struct}$ and a text similarity score $s_{text}$, then combine them:
    - $s = \alpha \cdot s_{struct} + (1-\alpha) \cdot s_{text}$, with $\alpha$ tunable by context or analyst preference.
    - This is easy to reason about and can be changed per use case (e.g., screening may rely more on structure, deep dives more on text).
- **Context-specific heads**: have different weighting schemes or small models for different "similar for what" contexts (e.g., "similar growth story," "similar risk pattern," "similar exit outcome"), each using the same underlying embeddings but different combination weights.

This approach keeps the system modular: embeddings are reusable assets, while similarity logic can evolve separately as analysts give feedback.

## Handling multi-modal nature in practice

Multi-modality is not just “combine numbers + text”; the system must let each modality shine when it is most informative:

- **Separate encoders per modality**: one encoder stack for structured features, one for long-form text, optionally another for tables extracted from PDFs if needed later.
- **Alignment and training**:
    - Use contrastive objectives where positive pairs are different views of the same deal (structured vs text) and negatives are random deals, so representations of the same underlying deal end up near each other in embedding space.
    - Use signals like "analyst considered these two deals during the same evaluation" or "deal A was used as a comp in memo for deal B" as additional positive pairs for training.
- **Modality-aware retrieval**:
    - Allow structured-only retrieval when the query is structured (e.g., a simple numeric filter from CRM).
    - Allow text-only retrieval when the query is free-form (e.g., “find roll‑up platforms with high customer concentration in healthcare IT”).
    - Use fused retrieval for the standard "find similar deals to this new CIM" workflow.

For the user experience, it is important that:

- Analysts can **see why** a deal was retrieved: show key aligned attributes (sector match, similar revenue and growth, same deal type) as well as highlighted memo snippets that drove text similarity.
- Analysts can adjust **sliders or presets** (e.g., "financial similarity high, sector similarity medium, memo similarity high"), which directly tweak the weights in the fusion function; those interactions are logged and used later to tune the model.

## Using feedback and evolution over time

Although this is more Part 2/3 territory, it ties back to representation:

- Every time an analyst clicks into, saves, or rejects a suggested similar deal, the system gets a labeled example of "this pair is more/less similar for this context."
- These labels can be used to:
    - Reweight structured vs text contributions.
    - Re-train projection layers that map raw embeddings into the similarity space.
    - Discover new latent factors (e.g., "recurring revenue + low churn + B2B mid-market" often co-occur in deals analysts consider comparable).

The embedding/representation stack is therefore not static; it starts with sensible defaults and gradually shifts to match the firm's actual notion of similarity as expressed in usage.

If you want, the next step could be to drill into a concrete similarity scoring function or walk through an end‑to‑end example for a new SaaS deal vs the historical portfolio.

<div align="center">⁂</div>

