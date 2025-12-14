<img src="https://r2cdn.perplexity.ai/pplx-full-logo-primary-dark%402x.png" style="height:64px;margin-right:32px"/>

# Technical Proposal: Part 3 - Practical Considerations (30%)

## 3.1 Evaluating System Effectiveness

**Quantitative metrics** track retrieval quality and business impact:
- **Precision@5/10**: % of top-k deals analysts mark "useful" (>70% target)
- **Recall@20**: % of deals analysts manually find that system surfaces
- **Time-to-insight**: Analyst survey (hours/week saved on comp research)
- **Coverage**: % of new CIMs with ≥3 relevant historical matches

**Offline evaluation** uses historical proxies:

```
Split historical deals into train/test
Query: "use deal X to find deal Y" where Y was evaluated near X
Hit rate: did system rank Y in top-5?
```

**A/B testing**: New vs old workflow; measure deal screening speed + decision confidence.

## 3.2 MVP vs Production System

| Phase | Timeline | Features | Tech Stack | Success Criteria |
| :-- | :-- | :-- | :-- | :-- |
| **MVP (4 weeks)** | Sprint 1-2 | Basic CRM sync + PDF text extraction<br>Off-the-shelf embeddings (sentence-transformers)<br>Cosine similarity + sector filter<br>Streamlit UI | Pinecone free tier<br>FastAPI<br>Local embedding models | 50% precision@5<br>10 analysts onboarded |
| **Beta (8 weeks)** | Sprint 3-6 | Multi-modal fusion<br>Feedback logging<br>Context presets (screening/risk)<br>Basic explainability | Custom projection layer<br>PostgreSQL metadata<br>Celery for batch jobs | 70% precision@5<br>Daily active users |
| **Production (12 weeks)** | Sprint 7-12 | Fine-tuned embeddings<br>Personalized weights<br>Audit logging + RBAC<br>API for deal pipeline | Kubernetes<br>Ray for distributed training<br>Enterprise vector DB | 80% precision@5<br>20% time savings validated |

## 3.3 Key Risks and Failure Modes

| Risk | Impact | Mitigation |
| :-- | :-- | :-- |
| **Poor initial similarity** | Analysts abandon system | Conservative MVP + weekly feedback syncs with power users |
| **Data quality** | Garbage embeddings | Robust ingestion validation + manual review queue for failed PDFs |
| **Regime shift** | 2022 SaaS ≠ 2025 SaaS | Temporal decay + macro flags; retrain quarterly |
| **Over-reliance** | Blind trust in AI | Always show "manual search" fallback + outcome disclaimers |
| **Adoption** | Analysts stick to email/CRM | Embed in existing workflow; gamify feedback ("top similarity curator") |
| **Privacy** | CIM confidentiality | On-prem deployment option; SOC2 compliance |

**Critical failure**: System always returns same 5 deals → **Diversity penalty** in ranking.

## 3.4 Handling Analyst Divergence

**When system ≠ analyst notion of similarity**:

```
1. Surface + log divergence: "You rejected top match - help improve?"
2. Per-analyst weights: Learn personal w_struct/w_text from interactions
3. "Override mode": Analyst pins deals → boosts those embeddings for their queries
4. Senior review: Flag low-confidence results (<0.6 score) for partner input
```

**Escalation workflow**:

```
Low confidence (<3 good matches):
→ "Limited comps found. Similar deals in adjacent sectors: [list]"
→ "Ask senior partner" button → routes to Slack/Teams
```

**Long-term alignment**: Quarterly "similarity workshop" where analysts vote on test cases to recalibrate system.

## 3.5 Deployment and Scaling

```
Infrastructure:
├── Data: 10K historical deals → ~10GB vectors (scalable to 100K)
├── Compute: Embedding inference ~2s/deal (A100 GPU batching)
├── Latency: <5s end-to-end query (including re-ranking)
└── Cost: ~$2K/month (vector DB + GPU inference)
```

**Phased rollout**:

1. **Power users** (deal team leads): Week 1-4
2. **Full analysts**: Week 5+ with training
3. **Banker portal** (read-only): Month 3

***

**Word count**: ~520
**Complete Part 3 coverage** - practical, measurable, risk-aware.
<div align="center">⁂</div>
