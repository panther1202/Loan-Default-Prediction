---
title: Test & Evaluation Strategy
status: draft
tags: [testing, evals]
date: 2026-09-03
---

# Test & Evaluation Strategy

## Testing pyramid, adapted for an LLM-integrated system

```
        /  E2E  \         Live deployed endpoint, fixed applicant cases, full pipeline
       / Integration \     RAG relevance, agent tool-call sequencing, grounding/hallucination checks
      /  Unit Tests   \    Schema compliance, attribution math, prompt-template rendering
```

Unlike a pure-ML pyramid, "coverage" here includes non-deterministic LLM output — tests must check *properties* of the output (schema validity, grounding, absence of protected-class factors), not exact string equality.

## What to cover, by stage

### Stage 1 — Explainability layer
- **Unit:** JSON schema validation on every LLM response (100% of calls must parse against the defined schema — no exceptions, no silent fallback to free text).
- **Unit:** Attribution computation (`coefficient × standardized/dummy value`, per [[0005-ml-model-hosting]]) tested independently of the LLM — given fixed inputs, does it return the expected top-N features deterministically, and does the TypeScript reimplementation's probability output match the original Python model's `predict_proba` within floating-point tolerance for a set of known test rows.
- **Integration:** Hallucination/grounding check — for a fixed set of test applicants, do the LLM's `primary_reasons` correspond (semantic match, not exact string) to the independently-computed top attributed features. Target: 100% pass on the fixed eval set before calling Stage 1 done.
- **Safety:** Explicit, named check — confirmed from the actual model export (`model_params.json`) — that `Age`, `MaritalStatus_Married`, and `MaritalStatus_Single` never appear in `primary_reasons` or `explanation_text`, across the full eval set. This isn't a generic placeholder anymore: `Age` is the model's single largest-magnitude coefficient (−0.588 of 26 features), so this check has real work to do, not just theoretical coverage.

### Stage 2 — RAG grounding
- **Integration:** Retrieval relevance — for a fixed set of queries, does the retrieved chunk actually relate to the query (manual-labeled relevance set, small — a dozen or so cases is enough at this scale).
- **Integration:** Citation presence — every explanation includes a traceable reference to the retrieved source chunk.
- **Regression:** Re-run Stage 1's grounding checks to confirm Stage 2 didn't regress explanation accuracy while adding citations.

### Stage 3 — Agent orchestration
- **Integration:** Tool-call sequencing — given an approval case, does the agent skip the explanation/RAG tools appropriately (or handle them per spec); given a denial case, does it call all required tools in a valid order.
- **Integration:** Failure handling — what happens if a tool call fails (e.g., RAG returns no relevant chunk, model tool times out) — must degrade gracefully, not silently fabricate.

### Stage 4 — Evaluation & observability
- **E2E:** Full request → notice, run against the deployed Cloudflare endpoint (not just local), confirming the real free-tier CPU/latency budget holds — this is the empirical check [[0004-deployment-platform]] and [[0005-ml-model-hosting]] both depend on.
- **Non-functional:** Cost check — confirm actual usage stays under Workers/Vectorize/D1/AI Gateway free-tier caps at expected demo traffic.
- **Regression:** All of the above rolled into a CI-run eval suite (GitHub Actions), so a change to a prompt or a retrieval parameter can't silently regress grounding accuracy without being caught before deploy.

## Coverage targets

- Schema compliance: 100% (hard requirement, not a target to approach).
- Grounding/hallucination check: 100% pass on the fixed eval set — **now a hard release gate, not a monitored metric**, since [[0006-frontend-framework-hosting]] means this content reaches the applicant with no human reviewing it first. A regression here should block deploy (CI gate), not just get logged for later review.
- Protected-class-factor check: 100% (hard requirement) — specifically `Age`, `MaritalStatus_Married`, `MaritalStatus_Single`, per [[0005-ml-model-hosting]].
- Portal disclaimer presence: the "learning simulation, not legal/compliance-reviewed language" disclaimer must render on every explanation view — add this as a simple frontend smoke test once the portal exists, not just a design intention.
- E2E latency/cost: pass/fail against the free-tier budget, measured, not assumed.

## Known gaps (explicit, not hidden)

- The fixed eval set's size and composition can't be finalized until real applicant data/feature schema is available from the repo.
- Stage 4's E2E latency numbers are meaningless until [[0005-ml-model-hosting]] is resolved — don't write this test until the hosting architecture is chosen.
- LLM non-determinism means "100% pass" assumes low/zero temperature (see [[0001-llm-provider]] action items) — if temperature is ever raised for other reasons, this test suite's pass-rate expectations need revisiting.

## Skip (per standard testing-strategy guidance)

- Trivial getters/setters and framework-generated code.
- Testing Cloudflare's own infrastructure (Workers runtime, Vectorize internals) — trust the platform, test the integration points.

## Related

[[Home]] · [[PRD]] · [[AI_SDLC_CHECKLIST]]
