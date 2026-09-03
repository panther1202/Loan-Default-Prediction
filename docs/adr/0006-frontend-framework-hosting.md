---
title: "ADR-0006: Frontend Framework & Hosting"
status: Accepted
tags: [adr, decision]
date: 2026-09-03
---

# ADR-0006: Frontend Framework & Hosting

**Status:** Accepted
**Date:** 2026-09-03
**Deciders:** Panth

## Context

The project has grown from "API-only, minimal form is enough" (original [[PRD]] non-goal, now superseded) to a proper applicant-facing self-service portal. It needs a real frontend framework and free hosting consistent with the rest of the Cloudflare-based stack ([[0004-deployment-platform]]).

## Decision

Use **SvelteKit** with `@sveltejs/adapter-cloudflare`, deployed on Cloudflare (Pages or Workers, via the adapter's build output), calling the existing API Worker ([[0004-deployment-platform]]) as its backend.

## Options Considered

### Option A: SvelteKit
| Dimension | Assessment |
|---|---|
| Cost | Free — same Cloudflare account, no new vendor |
| Learning value | Real modern framework (routing, SSR/CSR, reactivity, stores) without React's boilerplate/state-management overhead |
| Cloudflare fit | First-class Cloudflare adapter; deploys cleanly alongside the existing Worker |

**Pros:** Lighter mental model than React while still being a real, current framework choice; strong Cloudflare deployment story.
**Cons:** Smaller ecosystem/job-market footprint than React — a fair trade here since the project's learning target is the AI-engineering roadmap, not frontend framework breadth.

### Option B: React + Vite (not chosen)
More in-demand as a standalone frontend skill, but adds component-state and build-tooling complexity on top of an already multi-part project (agent orchestration, RAG, evals). Would compete for attention with the actual learning target.

### Option C: Lightweight no-build HTML/TS (not chosen)
Simplest possible, but the user explicitly wants "a good proper UI," which this option is not designed to deliver well.

## Trade-off Analysis

Given the project's primary goal (roadmap.sh/ai-engineer skills, not frontend framework mastery), SvelteKit is the right middle ground: real framework experience and a genuinely good UI are achievable without the framework itself becoming the bulk of the work, unlike Option B.

## Consequences

- The portal is a separate deployable (SvelteKit app) from the API Worker, calling it over HTTP — CORS must be configured on the Worker for the portal's origin.
- **This portal delivers the AI-generated explanation directly to the applicant, with no human review step in between.** This raises the bar on [[TEST_STRATEGY]]'s eval suite from "monitored metric" to "hard release gate," and requires the "learning simulation, not legal/compliance-reviewed language" disclaimer to be visible in the UI itself, not just in documentation.
- **Identity/lookup simplification:** the portal identifies an applicant by Loan ID lookup against the demo dataset, not real authentication. This is a deliberate scope simplification for a learning project, not a production-auth decision — flagged explicitly rather than silently assumed, per [[PRD]]'s existing "no auth/billing system" non-goal (now narrowed, not removed).

## Action Items
1. [ ] Scaffold the SvelteKit app with the Cloudflare adapter once frontend work begins.
2. [ ] Configure CORS on the API Worker for the portal's origin.
3. [ ] Design (visual/UX — being handled separately, not by this ADR) must surface the disclaimer prominently, not as fine print.

## Related

[[Home]] · [[PRD]] · [[0004-deployment-platform]] · [[TEST_STRATEGY]] · [[IMPLEMENTATION_PLAN]]
