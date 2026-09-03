---
title: "ADR-0001: LLM Provider"
status: Accepted
tags: [adr, decision]
date: 2026-09-03
---

# ADR-0001: LLM Provider

**Status:** Accepted
**Date:** 2026-09-03
**Deciders:** Panth

## Context

The project needs an LLM for (a) structured-output generation of explanations grounded in feature attribution, and later (b) function/tool-calling for agent orchestration. It must be usable at $0/month and support strict schema-constrained output.

## Decision

Use **Google AI Studio / Gemini API** for all LLM calls (explanation generation, later tool-calling).

## Options Considered

### Option A: Gemini API (Google AI Studio)
| Dimension | Assessment |
|---|---|
| Cost | Free tier available, no card required to start |
| Structured output | Native `response_schema` / JSON mode support |
| Tool-calling | Native function-calling support, needed for Stage 3 |
| Team familiarity | User has existing Google AI Studio access |

**Pros:** Already has access; native structured output and function calling; free tier fits a demo project.
**Cons:** Free-tier rate limits (verify current limits at build time — they change); vendor lock-in to Gemini's API shape.

### Option B: OpenAI API
| Dimension | Assessment |
|---|---|
| Cost | No meaningful indefinite free tier — paid from near-zero usage |
| Structured output | Native JSON schema support |
| Tool-calling | Native, mature |

**Pros:** Mature tool-calling ecosystem, widely documented.
**Cons:** Fails the $0/month constraint outright — disqualifying for this project.

### Option C: Local open-source model (e.g., via Ollama)
| Dimension | Assessment |
|---|---|
| Cost | Free (compute cost only) |
| Structured output | Unreliable without extra constrained-decoding tooling |
| Tool-calling | Weak/inconsistent for small open models |
| Deployability | Cannot run inside a Cloudflare Worker or a free-tier host without a GPU — needs its own always-on host |

**Pros:** Zero API cost, no vendor rate limits.
**Cons:** Structured-output and tool-calling reliability is the weak point for exactly the two capabilities this project needs most (Stages 1 and 3); adds its own hosting problem on top of the [[0005-ml-model-hosting|ADR-0005]] hosting problem already open.

## Trade-off Analysis

Option B is disqualified by the $0 constraint. Option C's structured-output/tool-calling unreliability directly undermines the two hardest, most valuable roadmap skills this project targets (structured output, agentic tool use) — it would teach worse habits (looser parsing, retry logic to paper over unreliable output) rather than the intended skills. Option A best fits both the cost constraint and the specific capabilities needed.

## Consequences

- All prompts must be written against Gemini's `response_schema` / function-calling conventions.
- Free-tier rate limits must be checked at implementation time (not assumed from this document) and designed around (e.g., caching via Cloudflare AI Gateway — see [[0003-observability|ADR-0003]]).
- If Gemini's free tier terms change materially, revisit this ADR before continuing.

## Action Items
1. [ ] Confirm current Gemini free-tier rate limits and available model names at implementation time.
2. [ ] Store `GEMINI_API_KEY` as a Cloudflare Worker secret, never committed.

## Related

[[Home]] · [[PRD]] · [[0003-observability]] · [[0005-ml-model-hosting]]
