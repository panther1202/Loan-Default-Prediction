---
title: "ADR-0005: ML Model & Explainability Hosting"
status: Accepted
tags: [adr, decision]
date: 2026-09-03
---

# ADR-0005: ML Model & Explainability Hosting

**Status:** Accepted — resolved by inspecting the actual repo (see Confirmed Findings).
**Date opened:** 2026-09-03. **Date accepted:** 2026-09-03.
**Deciders:** Panth

## Context

The existing loan-default model needed identifying before this ADR could close — see the original three options below, written before repo access.

## Confirmed findings (from the actual repo)

- `app.py` is training/EDA code only — it trains seven candidate models (Logistic Regression, KNN, Naive Bayes, Decision Tree, Random Forest, Gradient Boosting, Calibrated Linear SVM), scores each by test ROC-AUC, and pickles whichever wins. **There is no existing serving/inference script** — Stage 1 has to build one, not integrate with one.
- The saved artifact (`logistic_regression_loan_default_model.pkl`) confirms Logistic Regression won. Loaded directly: `sklearn.linear_model.LogisticRegression`, `solver='liblinear'`, `penalty='l2'`, `C=1.0`, `class_weight='balanced'`, 26 coefficients, one intercept.
- Preprocessing is `StandardScaler` (11 numeric features) + `OneHotEncoder(drop='first')` (7 categorical columns → 15 dummy columns) = 26 total features, matching `default_model_feature_names.pkl` exactly.
- Preprocessing has one more step than the first export captured: `app.py` clamps every raw numeric column to IQR bounds (Q1 - 1.5*IQR, Q3 + 1.5*IQR) before deriving `EstimatedEMI`/`Payment_to_Income_Ratio` and before the scaler is fit. Those bounds are now exported to `model_params.json.outlier_bounds`, reproducibly, by `export_model_params.py`. Measured impact: **zero rows of the training data fall outside any bound**, so the capping was a no-op at training time and does not affect scaler parity (the replay in that script asserts all 22 scaler statistics match the committed export to `rtol=1e-9`). It matters only for serving inputs outside the training range, which the Stage 5 application form can accept. Treat it as input handling, not as a fidelity fix.
- Related and not yet addressed: the model was never trained outside the observed ranges (`Age` 18-69, `Income` 15,000-149,999, `LoanAmount` 5,000-249,999, `CreditScore` 300-849, `MonthsEmployed` 0-119, `NumCreditLines` 1-4, `InterestRate` 2.0-25.0, `LoanTerm` 12-60, `DTIRatio` 0.1-0.9). Clamping keeps the arithmetic in-domain but does not make a prediction on an out-of-range applicant meaningful. Stage 5 needs real input validation on its own account.
- This is a genuinely linear model on a fixed, fully-inspected feature pipeline — every number needed for exact attribution is now exported to `model_params.json` (coefficients, intercept, scaler mean/scale, encoder categories, derived-feature formulas for `EstimatedEMI` and `Payment_to_Income_Ratio`).
- **Compliance flag, not hedged:** `Age` and `MaritalStatus` are model input features. `Age` has the single largest coefficient magnitude of all 26 features (−0.588) — it is the model's top predictor. Both `Age` and marital status are protected bases under ECOA/Regulation B. This doesn't block using the existing model (retraining it is out of scope per the PRD), but it makes the Stage 1 "never cite a protected-class factor" rule load-bearing rather than a formality — the model's most important feature by weight is one the explanation layer must never surface as a reason.

## Decision

**Option C — the model already is linear; no simplification or retraining needed.** Attribution is computed as exact math in TypeScript directly in the Worker: `contribution[f] = coefficient[f] × standardized_or_dummy_value[f]`, decision probability = `sigmoid(intercept + Σ contributions)`. This is not an approximation — it is the same math `coef_ × X` that produces the model's own decision, just computed outside sklearn.

## Options Considered (as originally framed, before repo access)

### Option A: ONNX in the Worker
Superseded — unnecessary. ONNX conversion exists to run a model sklearn can't easily export to hand-written math (tree ensembles, anything with branching). A 26-coefficient logistic regression doesn't need it; hand-written arithmetic is simpler, has zero conversion/parity-testing risk, and is trivially auditable.

### Option B: Split the model out to a second host
Superseded — unnecessary for the same reason. This existed to preserve real SHAP for a model where SHAP is expensive to compute (tree ensembles). For a linear model, "real SHAP" and "coefficient × value" are the same computation — there's no fidelity to preserve by adding a second host.

### Option C: Simplify to a model where exact attribution is cheap
**Selected.** Originally written as "retrain if necessary" — no retraining was necessary, the deployed model already satisfies this option's conditions.

## Trade-off Analysis

This resolves cleanly once the fact this ADR was blocked on became known: the model is linear. No trade-off remains to weigh — Option C strictly dominates A and B on every dimension (cost, complexity, latency, fidelity) once the "is it linear" question is answered yes.

## Consequences

- Stage 1 (see `docs/IMPLEMENTATION_PLAN.md`) runs entirely inside the Cloudflare Worker, in TypeScript, using `model_params.json` as a static constant — no second host, no ONNX conversion, no Python at runtime.
- Stage 1 must also implement the preprocessing pipeline (derived features, scaling, one-hot encoding) faithfully in TypeScript, since no serving code existed to reuse — including the outlier clamp, which runs first, before the derived features — `model_params.json` carries everything needed to do this exactly.
- The eval suite (`docs/TEST_STRATEGY.md`) gets a concrete, named check: explanations must never cite `Age`, `MaritalStatus_Married`, or `MaritalStatus_Single`, even though `Age` is the model's strongest single predictor.

## Action Items
1. [x] Get repo access; identify model framework, type, and feature schema.
2. [x] Confirm model is linear; exported exact parameters to `model_params.json`.
3. [ ] Implement the TypeScript preprocessing + scoring pipeline from `model_params.json` in Stage 1, and unit-test it against known predictions from the Python model to confirm numerical parity before trusting it in the explanation layer.
4. [ ] Wire the protected-feature exclusion check into the eval harness before Stage 1 is considered done.

## Related

[[Home]] · [[PRD]] · [[0004-deployment-platform]] · [[TEST_STRATEGY]] · [[IMPLEMENTATION_PLAN]]
