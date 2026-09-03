---
title: "ADR-0004: Compute & Deployment Platform"
status: Accepted
tags: [adr, decision]
date: 2026-09-03
---

# ADR-0004: Compute & Deployment Platform

**Status:** Accepted
**Date:** 2026-09-03
**Deciders:** Panth

## Context

The project must deploy to production at $0/month, per explicit user requirement, on Cloudflare.

## Decision

Deploy the API/orchestration/agent layer as **Cloudflare Workers** (TypeScript), managed via **Wrangler**, with **GitHub Actions** running tests on push and deploying on merge to main.

## Options Considered

### Option A: Cloudflare Workers + Wrangler + GitHub Actions
| Dimension | Assessment |
|---|---|
| Cost | Workers free tier: 100K requests/day, 10ms CPU/invocation ([source](https://agentdeals.dev/vendor/cloudflare-workers)); GitHub Actions free minutes cover this easily at demo scale |
| Integration | Native to every other ADR in this project ([[0002-vector-store]], [[0003-observability]] both bind directly to Workers) |
| Language | TypeScript/JavaScript (or Python Workers — see caveat below) |

**Pros:** Single coherent platform for compute, vector store, DB, and LLM gateway; free CI/CD.
**Cons:** 10ms CPU/invocation is a real, tight constraint that directly shapes [[0005-ml-model-hosting|ADR-0005]]; language shift to TypeScript if the team's existing Python habits (e.g. the earlier Claude Code brief, written assuming `google-genai` Python SDK) aren't revised accordingly.

### Option B: Traditional container host (e.g., Fly.io/Render free tier) instead of Workers
| Dimension | Assessment |
|---|---|
| Cost | Free tiers exist but are typically more limited/aggressive about spin-down than Cloudflare's request-based model |
| Integration | Would still need Cloudflare only for DNS/CDN, losing the native Vectorize/D1/AI Gateway bindings |

**Pros:** Full Python runtime, no CPU-per-invocation cap in the same way.
**Cons:** Explicitly contradicts the user's stated requirement to deploy on Cloudflare; loses the tight integration with ADRs 2 and 3.

## Trade-off Analysis

Option B is disqualified by the explicit "deploy on Cloudflare" constraint. Within Option A, the 10ms CPU limit is a real risk factor rather than a solved problem — this ADR accepts Workers as the platform, but explicitly does **not** claim every component (especially the ML model + SHAP) will fit inside it. That question is deliberately deferred to [[0005-ml-model-hosting|ADR-0005]] rather than glossed over here.

## Consequences

- The agent/RAG/orchestration layer is implemented in TypeScript, not Python — a deviation from the earlier Python-oriented implementation brief, which must be revised once this ADR and [[0005-ml-model-hosting|ADR-0005]] are both settled.
- Every component's actual CPU time must be measured (`wrangler dev` local profiling, then real deployment metrics) before assuming it fits the free tier — this is a testable claim, not an assumption (see [[TEST_STRATEGY]]).
- GitHub Actions workflow needs a Cloudflare API token stored as a repo secret for deploy step.

## Action Items
1. [ ] Scaffold a Wrangler project once the repo is available, confirming compatibility with existing repo structure.
2. [ ] Set up GitHub Actions: test job on every push, deploy job on merge to main, gated on tests passing.
3. [ ] Benchmark actual CPU time per request once Stage 1 exists, before assuming the free tier holds.

## Related

[[Home]] · [[PRD]] · [[TEST_STRATEGY]] · [[0002-vector-store]] · [[0003-observability]] · [[0005-ml-model-hosting]]
