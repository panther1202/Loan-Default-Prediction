---
title: Loan Default AI Layer — Project Charter
status: in-progress
tags: [project, prd]
date: 2026-09-03
---

# Project Charter — Loan Default Prediction: AI Engineering Layer

**Status:** In progress — model architecture and frontend architecture both resolved; implementation not yet started.

## 1. Problem

An existing project already solves loan-default prediction with classical ML (frozen, trained, out of scope to retrain — confirmed `sklearn.LogisticRegression`, 26 features, see [[0005-ml-model-hosting]]). It has zero AI-engineering component. This project adds an LLM-powered layer on top of it, mapped to the roadmap.sh/ai-engineer curriculum, built to production-grade engineering standards, deployed at $0/month on Cloudflare, with a proper applicant-facing self-service portal ([[0006-frontend-framework-hosting]]).

The concrete AI task is not "predict default" (already solved) — it is: **generate a grounded, structured, human-readable explanation of the model's decision, retrieve supporting policy language for it, and orchestrate that whole pipeline through an agent**, with evaluation and observability around all of it, delivered directly to the applicant through a self-service portal.

## 2. Business framing (real-world anchor, not just a demo)

US lenders must give rejected applicants specific reasons for denial (ECOA / Regulation B, adverse-action notices). This project simulates that pipeline: model decision → real feature attribution → LLM explanation grounded in that attribution → RAG-sourced policy citation → agent orchestration → logged, evaluated output → shown directly to the applicant in a self-service portal.

**Explicit disclaimer, restated everywhere it matters — now including the UI itself:** this is a learning simulation. No claim is made that the generated notices are legally sufficient; real deployment would need compliance/legal review.

**Elevated by the applicant-facing portal decision ([[0006-frontend-framework-hosting]]):** the AI-generated explanation reaches the applicant directly, with no human reviewing it first. That makes two things non-negotiable rather than aspirational: (1) the disclaimer must be visible in the portal UI itself, not only in docs/code comments; (2) [[TEST_STRATEGY]]'s grounding/hallucination eval suite is the only safety net before this content reaches a real person — treat it as a hard release gate, not a monitored metric.

## 3. Scope

In scope:
1. Explainability layer — LLM turns real per-instance feature attribution into a structured explanation (JSON schema, not free text), computed as exact linear-model arithmetic (no SHAP library needed — see [[0005-ml-model-hosting]]).
2. RAG layer — retrieval over a small policy/regulatory corpus so explanation language is grounded, with citations.
3. Agent layer — tool-calling orchestration: predict → attribute → retrieve → draft, decided by the agent, not a fixed script.
4. Eval + observability — schema-compliance checks, hallucination/grounding checks against a fixed case set (treated as a hard release gate, not a monitored metric), prompt/response logging, cost and latency tracking, protected-feature exclusion checks (`Age`, `MaritalStatus_*`).
5. Deployment — live, callable Cloudflare service, $0/month at demo traffic.
6. Applicant-facing self-service portal (SvelteKit, [[0006-frontend-framework-hosting]]) — Loan ID lookup, decision + explanation + citations display, visible disclaimer.

Out of scope (explicit, so scope doesn't creep):
- Retraining or improving the underlying ML model's accuracy **as part of the AI layer's own work**. This is no longer excluded outright: per [[0008-model-change-policy]] the model may be changed, and additional training datasets added, through an explain-then-approve gate. What stays out of scope is changing it *incidentally* while building the AI layer.
- Legally-certified compliance output — this is a learning simulation, restated in the UI itself, not just this document.
- Real authentication — the portal uses Loan ID lookup against the demo dataset, not login/credentials. Deliberate simplification, not an oversight.
- What-if/counterfactual scoring, fairness red-teaming evals, a drift-monitoring dashboard, and population-comparison context in explanations (see [[IMPLEMENTATION_PLAN]]'s Phase 2) — considered and explicitly deferred (not rejected) in favor of shipping the core 4-stage pipeline plus portal first.

## 4. Success criteria

- All four capability layers (explainability, RAG, agent, evals) run end-to-end and are independently demoable, plus the portal calling them.
- Eval suite: schema-valid output on 100% of fixed test cases; cited reasons match independently-computed feature attribution on 100% of fixed test cases; zero occurrences of `Age`/`MaritalStatus_*` in any generated explanation.
- Deployed service responds within Cloudflare free-tier limits — [Certain] Workers free tier is 100K requests/day and 10ms CPU time per invocation ([source](https://agentdeals.dev/vendor/cloudflare-workers)) — verified empirically per component, not assumed.
- Total infrastructure cost: $0/month at demo-level traffic.

## 5. Constraints

- LLM: Google AI Studio (Gemini API), free tier. See [[0001-llm-provider]].
- Deployment: Cloudflare (Workers + associated free services). See [[0004-deployment-platform]].
- Frontend: SvelteKit on Cloudflare, applicant-facing. See [[0006-frontend-framework-hosting]].
- Tooling: current, in-demand, free — no paid SaaS.
- Underlying ML model: confirmed `sklearn.LogisticRegression`, 26 features, exact parameters exported to `model_params.json`. See [[0005-ml-model-hosting]]. Frozen by default and changeable only through the gate in [[0008-model-change-policy]].

## 6. Open decisions

None blocking implementation start. [[0007-approval-decision-and-suggestions]]'s parameters were the last open set and were confirmed on 2026-09-03 (threshold `P(default) ≤ 0.37`, quintile credit bands, a 400bps rate card, no term surcharge, `LoanTerm` dropped from the denial-suggestion allow-list) — each measured against the real dataset rather than assumed, see that ADR's Evidence section. Visual/UX design of the portal is being handled separately (outside this vault, by the user directly) and is not tracked here as an open decision — only its architectural shape ([[0006-frontend-framework-hosting]]) is.

## 7. Process

Following an AI-SDLC checklist (user-supplied), adapted for this project's actual shape (integration of pretrained models around a frozen classical model, not training a new model). See [[AI_SDLC_CHECKLIST]] for the phase-by-phase mapping. Documentation (this note + ADRs + [[TEST_STRATEGY]]) is written and reviewed before implementation begins, per the phase gates in that mapping.

## Related

[[Home]] · [[AI_SDLC_CHECKLIST]] · [[TEST_STRATEGY]] · [[IMPLEMENTATION_PLAN]] · [[0001-llm-provider]] · [[0002-vector-store]] · [[0003-observability]] · [[0004-deployment-platform]] · [[0005-ml-model-hosting]] · [[0006-frontend-framework-hosting]] · [[0007-approval-decision-and-suggestions]]
