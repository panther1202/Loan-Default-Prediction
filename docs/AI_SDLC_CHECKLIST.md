---
title: AI-SDLC Checklist — Mapped to This Project
status: in-progress
tags: [process, sdlc, checklist]
date: 2026-09-03
---

# AI-SDLC Checklist — Mapped to This Project

Source checklist: [[ai_sdlc_checklist_source|user-supplied AI-SDLC checklist]] (7-phase generic AI System Development Life Cycle). Below, every item is marked:

- **Applies** — do it as written
- **Adapted** — the checklist assumes a different shape of project (training a model from scratch); here's the equivalent action for integrating pretrained models around a frozen classical model
- **N/A** — genuinely doesn't apply, with the reason stated (not silently skipped)

Treat this note as the phase-gate tracker: each phase's items should be checked before moving to the next, same as the original checklist intends. See [[PRD]] for the project this maps onto.

## Phase 1: Business Alignment & Feasibility

- [ ] **Problem Definition** — Applies. Concrete AI task: grounded explanation generation + RAG retrieval + agentic orchestration around an existing classifier. See [[PRD]] §1.
- [ ] **Success Metrics** — Applies. See [[PRD]] §4 (schema validity rate, hallucination/grounding rate, latency within free-tier CPU budget, $0 cost).
- [ ] **Feasibility Study** — Applies, with a twist: the constraint isn't data volume (RAG corpus is intentionally small) or budget (target is $0) — it's **Cloudflare's free-tier CPU/runtime limits against the model's actual inference + explanation cost**. This is exactly [[0005-ml-model-hosting]]. Feasibility here means: benchmark before committing to an architecture, not after.

## Phase 2: Data Engineering & Governance

- [ ] **Data Collection** — Adapted. No new training data is being collected. "Data" in this project is (a) the small RAG corpus of policy/regulatory text, and (b) a fixed set of applicant test cases for evals. Collect/draft both explicitly.
- [ ] **Data Auditing & Cleaning** — Adapted. Applies to the RAG corpus only: no duplicate chunks, no contradictory policy statements, source each chunk.
- [ ] **Data Labeling** — N/A. No supervised training is happening in this project; the underlying classifier was already trained and is frozen. (If the original ML project's own training data ever needs re-auditing, that's a different, earlier project — out of scope here.)
- [ ] **Feature Engineering** — N/A for this layer. The feature schema is inherited as-is from the existing frozen model (out of scope to change). What *is* in scope: correctly reading and reusing that existing feature schema for attribution (Stage 1) — a verification task, not a feature-engineering task.
- [ ] **Compliance Check** — Applies, narrowed: this project doesn't collect new personal data, but the *output* (adverse-action-style language) is exactly the kind of content ECOA/Reg B governs. Compliance check here = the explicit "learning simulation, not legal advice" disclaimer in every relevant doc and in the generated output itself, plus: never let the LLM cite a protected-class factor (race, sex, age proxies, etc.) as a reason — add this as an explicit eval check, not just a hope.

## Phase 3: Model Selection & Design

- [ ] **Architecture Selection** — Applies, already decided: integrate a commercial vendor API (Gemini) rather than building or fine-tuning a model. See [[0001-llm-provider]].
- [ ] **Baseline Establishment** — Adapted. The "baseline" isn't a simple heuristic to beat with a new model — the existing frozen ML model *is* the baseline being explained. The equivalent baseline for the new AI layer: a naive, non-grounded LLM explanation (no attribution input, no RAG) as the control to demonstrate why grounding (Stage 1) and citation (Stage 2) actually matter. Worth building once, briefly, purely to show the before/after in the eval results.
- [ ] **Compute Allocation** — Adapted. No training compute needed. Real question: does inference (model + attribution + LLM call + retrieval) fit Cloudflare's free-tier CPU budget? This is [[0005-ml-model-hosting]] again — the compute question in this project is a *hosting* question, not a *training hardware* question.

> **Conditional on the model staying frozen.** The N/A markings in Phases 2 and 4 below rest on "no training happens in this project." Per [[0008-model-change-policy]] that is now a default rather than a permanent constraint: an approved retrain or an added dataset reactivates those items for the scope of that change, and they are then worked through rather than inherited as N/A.

## Phase 4: Iterative Development & Training

- [ ] **Data Splitting** — N/A. No model is being trained in this project.
- [ ] **Model Training** — N/A. Same reason. (If this ever becomes "also improve the base classifier," that's a new phase-3/4 cycle for the *original* ML project, tracked separately from this AI-layer project.)
- [ ] **Hyperparameter Tuning** — N/A, no training. The closest analog that *does* apply: tuning LLM call parameters (temperature, top-p) for the explanation layer — low/zero temperature for consistency, since this is a decision-explanation task, not a creative one. Track this as a small config decision, not a full HPO cycle.

## Phase 5: Evaluation & Testing

- [ ] **Technical Evaluation** — Applies. See [[TEST_STRATEGY]]: schema-compliance rate, grounding/hallucination rate, retrieval relevance.
- [ ] **Safety & Bias Auditing** — Applies, and important here specifically: test that explanations never surface protected-class factors as reasons, test edge cases (borderline approve/deny scores, missing features), test for hallucinated numbers.
- [ ] **User Acceptance Testing (UAT)** — Adapted, and tightened by a later decision: the project now includes an applicant-facing self-service portal ([[0006-frontend-framework-hosting]]), which means there is **no human review step between the LLM's output and the person it's about** — the original "dark launch, compare before exposing" plan still applies during development (run in shadow mode against the fixed eval set before wiring the portal to live output), but once the portal ships, the eval suite in [[TEST_STRATEGY]] is the only thing standing between a hallucinated explanation and a real applicant. Don't treat this UAT item as satisfied by "we ran it in shadow mode once" — the eval suite needs to keep passing on every change, permanently, not just at the initial cutover.

## Phase 6: Deployment & Integration (MLOps)

- [ ] **CI/CD Automation** — Applies. GitHub Actions running tests on push, deploying to Cloudflare on merge to main. See [[0004-deployment-platform]].
- [ ] **Inference Optimization** — Adapted, conditional on [[0005-ml-model-hosting]]: if the ONNX-in-Worker path is chosen, quantization/model-size reduction may matter to fit the CPU budget; if the split-host path is chosen, this item is largely N/A since the model runs on a normal (non-edge) free host with no CPU-per-invocation cap.
- [ ] **API Exposure** — Applies. Cloudflare Worker is the API surface; "secure microservice framework" becomes "Worker + Wrangler," with the split-host option (if chosen) exposing its own small API behind it.

## Phase 7: Monitoring & Maintenance

- [ ] **Data Drift Tracking** — Adapted. Relevant to the *underlying frozen model's* input distribution (are incoming applicant profiles drifting from its training data) — worth a lightweight check, but note this is inherited risk from the original ML project, not something this AI layer introduces or can fix on its own.
- [ ] **Concept Drift Tracking** — Adapted, same caveat as above — flag it, don't over-invest, since retraining the base model is explicitly out of scope for this project.
- [ ] **Feedback Loops** — Applies, and this is a good real target: log every case where a generated explanation fails a grounding/hallucination check in production, route those into the fixed eval set so the test suite grows from real failures instead of staying static.

## What this means for sequencing

Phases 2 and 4 are mostly N/A/adapted — don't let that read as "skip ahead." Phase 1 (see [[PRD]]) and the ADRs still gate everything else, per the user's requested doc-first process. The real work starts at Phase 3 (architecture, already mostly decided via ADRs 1–4, blocked on [[0005-ml-model-hosting]]) and Phase 5 (eval design, can be drafted now, run once implementation exists).

## Related

[[Home]] · [[PRD]] · [[TEST_STRATEGY]] · [[0008-model-change-policy]]
