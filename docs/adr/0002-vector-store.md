---
title: "ADR-0002: Vector Store for RAG"
status: Accepted
tags: [adr, decision]
date: 2026-09-03
---

# ADR-0002: Vector Store for RAG

**Status:** Accepted
**Date:** 2026-09-03
**Deciders:** Panth

## Context

Stage 2 (RAG grounding) needs to embed and retrieve chunks from a small policy/regulatory corpus (expected: low tens of documents/chunks, not a large-scale corpus). Must be $0/month and ideally not add an extra vendor/host given the Cloudflare deployment target ([[0004-deployment-platform]]).

## Decision

Use **Cloudflare Vectorize** as the vector store.

## Options Considered

### Option A: Cloudflare Vectorize
| Dimension | Assessment |
|---|---|
| Cost | Free tier: 30M queried vector dimensions/month, 5M stored ([source](https://agentdeals.dev/vendor/cloudflare-workers)) |
| Integration | Native binding from a Cloudflare Worker — no network hop, no extra credentials |
| Scale fit | Massively over-provisioned for a corpus this small — headroom is not a concern |

**Pros:** Zero extra vendor, native Worker integration, free tier far exceeds this project's actual corpus size.
**Cons:** Ties retrieval logic to Cloudflare's API shape; less portable than a standalone vector DB if the project ever moves off Cloudflare.

### Option B: Self-hosted Chroma or FAISS
| Dimension | Assessment |
|---|---|
| Cost | Free, but needs an always-on host to serve queries |
| Integration | Requires a network call from the Worker to wherever it's hosted |

**Pros:** Fully portable, popular in RAG tutorials.
**Cons:** Requires its own free host, which is exactly the kind of extra moving part [[0004-deployment-platform|ADR-0004]] is trying to avoid for the parts of the system that don't need it. No benefit here since the corpus is small enough that Vectorize's free tier is not a real constraint.

### Option C: Pinecone (free tier)
| Dimension | Assessment |
|---|---|
| Cost | Has a free tier |
| Integration | External vendor, separate account/API key |

**Pros:** Purpose-built vector DB, well documented.
**Cons:** Adds a third-party account and credential for no capability Vectorize doesn't already provide at this scale.

## Trade-off Analysis

For a corpus this small, the deciding factor isn't vector-DB capability (all three are more than sufficient) — it's operational simplicity. Vectorize eliminates a network hop and a vendor relationship that Options B and C both require, at zero cost disadvantage.

## Consequences

- Retrieval code is written against Vectorize's API/binding, not a portable interface — acceptable given the project's scope, but note if reused elsewhere.
- Embeddings must be generated with a model compatible with Vectorize's dimension requirements — confirm chosen embedding model's output dimensions before indexing (Gemini embeddings vs. Workers AI's own embedding models are both options; pick one and be consistent between indexing and query time).

## Action Items
1. [ ] Decide embedding model (Gemini embedding API vs. Cloudflare Workers AI embedding model) once implementation starts — affects [[0001-llm-provider|ADR-0001]]/[[0004-deployment-platform|ADR-0004]] call patterns.
2. [ ] Draft and chunk the policy/regulatory corpus before indexing.

## Related

[[Home]] · [[PRD]] · [[0004-deployment-platform]]
