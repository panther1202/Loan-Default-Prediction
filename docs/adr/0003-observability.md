---
title: "ADR-0003: Observability & LLM Gateway"
status: Accepted
tags: [adr, decision]
date: 2026-09-03
---

# ADR-0003: Observability & LLM Gateway

**Status:** Accepted
**Date:** 2026-09-03
**Deciders:** Panth

## Context

Stage 4 requires logging every prompt/response, tracking latency and (theoretical) cost, and catching hallucinations/schema violations — a "production-grade" project needs this, not just working code. Must stay at $0/month.

## Decision

Route all Gemini calls through **Cloudflare AI Gateway**, and log structured eval/run data to **Cloudflare D1**.

## Options Considered

### Option A: Cloudflare AI Gateway + D1
| Dimension | Assessment |
|---|---|
| Cost | AI Gateway core features (caching, rate limiting, analytics) free; up to 100,000 logs/month free ([source](https://www.truefoundry.com/blog/cloudflare-ai-gateway-pricing-a-complete-breakdown)); D1 free tier: 5GB storage, 5M rows read/day, 100K rows written/day |
| Integration | Native to the Cloudflare stack already chosen — no extra vendor |
| Capability | Request/response logging, caching (cuts duplicate Gemini calls), rate limiting, analytics — directly satisfies the eval/observability requirement |

**Pros:** No new vendor, meaningful free-tier headroom for a demo project, caching reduces real Gemini API usage against free-tier rate limits.
**Cons:** Logging caps at 100K/month on the free plan — a real limit to watch, not likely to be hit at demo scale but worth monitoring.

### Option B: Third-party LLM observability (e.g., Langfuse free cloud tier)
| Dimension | Assessment |
|---|---|
| Cost | Free tier exists |
| Integration | External SDK, separate account/dashboard |

**Pros:** Purpose-built LLM observability UI, richer eval-tracking features than a generic gateway.
**Cons:** Adds a vendor and account outside the Cloudflare stack for a capability the native option already covers adequately at this project's scale.

### Option C: Bare console/D1 logging, no gateway
| Dimension | Assessment |
|---|---|
| Cost | Free |
| Capability | Manual logging only — no built-in caching, rate limiting, or analytics |

**Pros:** Simplest possible.
**Cons:** Reimplements, worse, what AI Gateway already provides for free — no reason to choose this over Option A.

## Trade-off Analysis

Option A wins on "no extra vendor" and "capability for the cost," which matters given the project's own constraint of staying inside a single free-tooling stack where possible. Option B is a reasonable alternative if richer LLM-specific eval dashboards become genuinely needed later — noted as a future revisit, not adopted now.

## Consequences

- All Gemini calls must be routed through the AI Gateway endpoint, not called directly — a small but non-optional integration detail.
- D1 schema needs to be designed for eval/run logs before Stage 4 implementation (see [[TEST_STRATEGY]]).
- Free-tier log cap (100K/month) should be monitored if this ever gets real traffic beyond demo use.

## Action Items
1. [ ] Set up an AI Gateway instance and route Gemini calls through it from the start (Stage 1), not retrofitted later.
2. [ ] Design D1 schema for run logs: timestamp, input hash, decision, cited reasons, schema-valid (bool), grounding-check-passed (bool), latency, cache-hit (bool).

## Related

[[Home]] · [[PRD]] · [[TEST_STRATEGY]] · [[0001-llm-provider]]
