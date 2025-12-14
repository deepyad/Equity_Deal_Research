<img src="https://r2cdn.perplexity.ai/pplx-full-logo-primary-dark%402x.png" style="height:64px;margin-right:32px"/>

# Technical Proposal: Part 2 - The Similarity Problem (40%)

## 2.1 Defining and Measuring Similarity

**Similarity is multi-dimensional and context-dependent**: Two deals are similar if they share economic, strategic, and risk profiles relevant to the evaluation context. Core metric: **weighted hybrid similarity score** combining structured, text, and metadata components:

```
s_struct = 1 - (||x_struct_1 - x_struct_2||_2 / √d)     // Normalized Euclidean (financials)
s_text = cosine(x_text_1, x_text_2)                      // Semantic document similarity  
s_meta = 0.2·sector_match + 0.1·geo_align + e^(-|Δyear|/5)  // Categorical + recency

s_final = w_struct·s_struct + w_text·s_text + s_meta     // w=[0.4, 0.6] initial
```

This captures: financial comparability (s_struct), business model/market alignment (s_text), and practical constraints (s_meta).

## 2.2 Context-Dependent Similarity ("Similar for What?")

**Multiple similarity modes** via adjustable weights or separate scorers:


| Context | w_struct | w_text | s_meta Focus | Example Query |
| :-- | :-- | :-- | :-- | :-- |
| **Screening** | 0.7 | 0.3 | Sector + Size | "Growth profiles in SaaS" |
| **Risk Assessment** | 0.2 | 0.7 | Geography | "Churn risks in enterprise software" |
| **Exit Potential** | 0.5 | 0.5 | Year + Outcome | "Similar multiples achieved" |
| **Strategic Fit** | 0.1 | 0.8 | Team/Fund | "Roll-up platforms in healthcare IT" |

**Implementation**: Analyst selects preset or sliders in UI → dynamically recompute rankings. Logs preferences for personalization.

## 2.3 Limitations of Pure Embedding-Based Similarity

**Key failure modes**:

- **Market regime shifts**: 2019 low-rate SaaS deals ≠ 2025 high-rate (handled via temporal decay).
- **Sparse data**: New subsectors lack historical comps (mitigate via sector hierarchies).
- **Outcome bias**: "Passed" deals may be retrospectively valuable (show all outcomes, flag reasons).
- **Black box**: Analysts reject unexplained matches (fix: per-modality attributions).
- **Semantic drift**: Embeddings miss firm-specific reasoning (e.g., "founder-led" nuance).

**Pure cosine fails when**:

```
Good match but different scales: $10M vs $100M revenue → low s_struct despite similar model
```


## 2.4 Incorporating Human Judgment and Feedback

**Online learning loop** turns analyst interactions into training signals:

```
1. Analyst views top-5 → clicks "useful"/"not useful" on deals
2. Log: (query_deal, historical_deal, label=+1/-1, context)
3. Batch → contrastive loss: pull useful pairs closer, push irrelevant apart
4. Update: projection layer weights w_struct/w_text + normalization params
```

**Cold-start handling**:

- Bootstrap with proxy labels: deals evaluated by same analyst/team
- "Deals used as comps" in memos (text-mined)
- Senior partner annotations (high-value signal)

**Evolution**:

```
Week 1: Off-the-shelf embeddings, fixed weights
Month 1: Feedback-tuned weights (w_text → 0.7 for SaaS deals)
Month 3: Custom projection head capturing "firm taste"
```

**Trust building**: Show **attribution breakdown** per result:

```
SecureNet (s_final=0.82)
├─ Financials: 0.85 (growth + margin match)
├─ Text: 0.78 ("churn stabilized via repricing")
└─ Meta: +0.15 (same sector, recent)
```


## 2.5 Edge Cases and Fallbacks

```
No good matches (>0.6 threshold): 
→ "Limited historical comps - consider adjacent sectors?"
→ Fall back to keyword + metadata search

Conflicting signals (high s_struct, low s_text):
→ Flag: "Financially similar but different business models"
→ Surface both for analyst judgment
```

**Evaluation**: A/B test vs manual search; precision@5 >70% where analysts mark results "saved time".

***


<div align="center">⁂</div>

