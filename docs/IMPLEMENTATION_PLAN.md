---
title: Implementation Plan — Staged Build
status: draft
tags: [implementation, plan]
date: 2026-09-03
---

# Implementation Plan — Staged Build

Supersedes the earlier standalone brief, which assumed a Python/`google-genai` stack. That assumption is wrong per [[0004-deployment-platform]] — this plan targets **TypeScript on Cloudflare Workers** throughout. [[0005-ml-model-hosting]] is now Accepted (confirmed `LogisticRegression`, 26 features) — Stage 1 below is written against that confirmed pipeline, not a branch of options.

## Step 0 — Orient in the real repo (done; recap for implementers)

`app.py` is training/EDA code only — it has no serving/inference path, so Stage 1 has to build one from scratch, not integrate with an existing endpoint. The trained artifacts are `logistic_regression_loan_default_model.pkl` (sklearn `LogisticRegression`), `default_feature_scaler.pkl` (`StandardScaler`, 11 numeric features), `default_one_hot_encoder.pkl` (`OneHotEncoder(drop='first')`, 7 categorical columns → 15 dummy columns), and `default_model_feature_names.pkl` (the 26-feature order the model expects). All of this has been exported once, exactly, to `model_params.json` (repo root) — coefficients, intercept, scaler mean/scale, encoder categories, and the derived-feature formulas for `EstimatedEMI` and `Payment_to_Income_Ratio`. Load that JSON as a static constant in the Worker; there is no need to re-derive any of these numbers from the `.pkl` files (which are Python/joblib-specific and not loadable from a Worker anyway).

## Stage 1 — Explainability layer

Goal: turn a raw applicant input into a decision and a compliant, structured explanation grounded in exact feature attribution — no SHAP library needed, because the model is linear.

**Pipeline (implement in this order, in TypeScript, using `model_params.json`):**
1. Compute derived features `EstimatedEMI` and `Payment_to_Income_Ratio` from the raw applicant fields, using the formulas in `model_params.json.derived_features`.
2. Standardize each of the 11 numeric features: `(raw - scaler.mean[f]) / scaler.scale[f]`.
3. One-hot encode each of the 7 categorical fields per `model_params.json.categorical_columns`: the applicant's category maps to `1.0` on its corresponding encoded column and `0.0` on the others; the `dropped_category` for that column means all-zeros.
4. Score: `logit = intercept + Σ(coefficients[f] × value[f])` over all 26 features; `probability_of_default = sigmoid(logit)`.
5. Attribution for explanation purposes: `contribution[f] = coefficients[f] × value[f]` — rank by absolute value to get the top-N drivers of this specific decision. This *is* the SHAP-equivalent value for a linear model, not an approximation of it.
6. **Before this feeds any LLM prompt, filter out `Age`, `MaritalStatus_Married`, and `MaritalStatus_Single` from the candidate reasons** — per [[0005-ml-model-hosting]], these are protected bases under ECOA/Reg B and must never be cited, even when (as is the case here) they rank among the top contributors.
7. Define a strict JSON schema for the LLM's output (`decision`, `primary_reasons`, `explanation_text`, `reason_codes`), call Gemini via its structured-output mode (`response_mime_type: application/json` + `response_schema`) through Cloudflare AI Gateway ([[0003-observability]]), with a system prompt that constrains the model to only phrase the (already-filtered) attribution values it was given — never invent a factor and never reintroduce a filtered one.

**Verification before moving to Stage 2:** run the TypeScript pipeline (steps 1–4) against a handful of rows also scored by the original Python model (`model.predict_proba`), and confirm the probabilities match within floating-point tolerance. This is the parity check named in [[TEST_STRATEGY]] — don't skip it, since a silent preprocessing mismatch (e.g. a mis-ordered one-hot column) would make every downstream explanation wrong in a way that's hard to notice by inspection.

Build the grounding test and the protected-feature exclusion test from [[TEST_STRATEGY]] alongside this stage, not after.

## Stage 2 — RAG grounding

**Gate: do not start implementing this stage from the paragraph below alone.** Stage 1 looked simple in outline too, right up until the rate-card/threshold-direction/scope discussion turned out to matter a lot ([[0007-approval-decision-and-suggestions]]). Stage 2 gets the same treatment — stop and discuss it at length with Panth before writing code: what actually goes in the policy corpus (real ECOA/Reg B text vs. an internally-authored lending policy vs. both), how the rate card from ADR-0007 factors in as a citable document, chunking strategy, and how retrieval failure (no relevant chunk found) should degrade rather than fail silently. The paragraph below is a placeholder sketch, not an approved design — treat it the way ADR-0005's three-option sketch was treated before repo access resolved it, not as something to build straight from.

Sketch (pending that discussion): build a small policy/regulatory text corpus, chunk it, embed it (pick one embedding model and use it consistently for indexing and querying — see [[0002-vector-store]] action items), index into Cloudflare Vectorize. Add a retrieval step that pulls the most relevant chunk(s) for a draft explanation and has the LLM revise its output to cite them. Extend the Stage 1 test to also check citation presence.

## Stage 3 — Agent orchestration

Define tools as plain TypeScript functions callable via Gemini's function-calling: `predictDefault`, `getFeatureAttribution`, `retrievePolicy`, `draftNotice`. Implement the tool-call loop directly against the Gemini API (not a framework like LangChain — the loop itself is the learning objective here) so the agent decides the sequence (e.g., skip explanation/RAG tools entirely for an approval).

## Stage 4 — Evaluation & observability

Formalize Stages 1–3's ad hoc checks into the fixed eval set from [[TEST_STRATEGY]], runnable in CI ([[0004-deployment-platform]]'s GitHub Actions job). Log every prompt/response/latency/cache-hit to the D1 schema from [[0003-observability]]. Add the CI gate: a prompt or retrieval change that regresses grounding accuracy should fail the build, not silently ship.

## Stage 5 — Applicant-facing portal

Goal: a proper self-service portal (SvelteKit, [[0006-frontend-framework-hosting]]), not a minimal form — visual/UX design is being handled separately by the user, this stage is the build once that design exists.

- **Correction from the original ADR-0006 assumption:** this is a fresh application form, not a Loan ID lookup — the applicant enters their own profile and desired loan from scratch (per the flow described in conversation), the system doesn't pull up an existing record. No real auth either way ([[0006-frontend-framework-hosting]]'s deliberate simplification) — there's just no identity to look up in the first place now.
- Calls the API Worker (Stages 1–3, plus the approval/rate-card/suggestion logic in [[0007-approval-decision-and-suggestions]] once its parameters are confirmed) to get decision, assigned rate/term, explanation, `primary_reasons`, suggestions (on denial), and citations; renders them.
- The "this is a learning simulation, not legal/compliance-reviewed language" disclaimer must be visibly rendered on every explanation view — not a footer afterthought. Cover this with the frontend smoke test in [[TEST_STRATEGY]].
- Configure CORS on the API Worker for the portal's deployed origin.
- Do not build this stage until the eval suite (Stage 4) is passing at 100% on the fixed set — per [[TEST_STRATEGY]], this content now reaches the applicant with no human review step, so the eval gate must be solid before it has a live audience.

## Phase 2 — Future Enhancements (after Stages 1–5 ship)

Not part of the current build — deliberately deferred until the core pipeline and portal are working end to end. Revisit this section then, don't pull items forward early.

### Population-comparison context for explanations

Idea: enrich the LLM-facing payload with deterministic statistics computed from `data/Loan_default.csv` (not from the model) — e.g. "this applicant's DTI ratio is higher than 78% of applicants in the historical dataset." This gives the LLM more *true* material to phrase without adding any new place for it to invent something, since it's still a precomputed fact handed to it, same as the attribution values are today.

Sketch, when this gets picked up:
- Compute percentile ranks for the handful of features worth comparing (`DTIRatio`, `CreditScore`, `Income`, `NumCreditLines`, `Payment_to_Income_Ratio`) against the historical population in the CSV — once, offline, not per-request.
- Export the result the same way `model_params.json` was exported (a static JSON of percentile breakpoints), so the Worker loads it as a constant — no new hosting/architecture, no live recomputation.
- Decide the comparison cohort deliberately before building this: all historical applicants, only historically-approved ones, or only applicants with the same decision as this one — each tells a different story and should be a stated choice, not a default nobody picked.
- Add to the LLM payload as additional structured facts (same schema-constrained approach as Stage 1's attribution), never as free-text summary the LLM writes itself.
- Extend [[TEST_STRATEGY]] with a check that any population-comparison statistic cited in an explanation matches the precomputed export — same grounding standard as everything else.

### Other deferred items (tracked in [[PRD]], not repeated here)

What-if/counterfactual agent tool, fairness red-team eval, and the drift-monitoring dashboard remain deferred per the original scoping discussion — see [[PRD]] §3.

## Suggested repo layout

Adapt to what Step 0 finds; a reasonable default for the Workers/TypeScript stack:

```
model_params.json   # exported once from the sklearn model — coefficients, scaler, encoder, formulas
src/
  predict.ts       # Stage 1: preprocessing + scoring pipeline against model_params.json
  explain.ts       # Stage 1: attribution + protected-feature filter + LLM structured explanation
  rag.ts           # Stage 2: corpus loading, embedding, Vectorize retrieval
  agent.ts         # Stage 3: tool definitions + orchestration loop
  index.ts         # Worker entry point
evals/
  cases.json       # fixed test applicants + expected top features (+ parity check vs. Python model)
  run_evals.ts
policy_corpus/      # sample policy/regulatory text for RAG
wrangler.toml
portal/              # SvelteKit app (Stage 5) — separate deployable, calls the API Worker
```

## Related

[[Home]] · [[PRD]] · [[AI_SDLC_CHECKLIST]] · [[TEST_STRATEGY]] · [[0001-llm-provider]] · [[0002-vector-store]] · [[0003-observability]] · [[0004-deployment-platform]] · [[0005-ml-model-hosting]]
