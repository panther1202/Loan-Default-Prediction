---
title: "ADR-0008: Model Change & Dataset Expansion Policy"
status: Accepted
tags: [adr, decision]
date: 2026-09-03
---

# ADR-0008: Model Change & Dataset Expansion Policy

**Status:** Accepted
**Date:** 2026-09-03
**Deciders:** Panth

## Context

[[PRD]] §3 listed "retraining or improving the underlying ML model's accuracy" as out of scope, and [[0005-ml-model-hosting]] treats the classifier as frozen. That framing was correct for scoping the AI layer, but it is no longer what Panth wants as a permanent constraint. Two changes, stated on
2026-09-03:

1. Changes to the current model implementation **are** permitted where they improve the project or produce better outcomes for the applicant — but each change must be explained and approved before it is made, not decided by the implementer and reported afterwards.
2. Additional datasets are being sourced to extend the training data.

Both matter now rather than later, because [[0007-approval-decision-and-suggestions]] was just parameterised against measurements taken from the *current* model over the *current* dataset. Every number in that ADR's Evidence section — band quintiles, approval rates, suggestion rescue rates, the `EstimatedEMI` sign quirk — is a property of what is in the repo today, not a derived truth. Without a stated policy, a retrain or a dataset addition would silently invalidate a set of decisions that look settled.

There is also a hazard specific to this project: the frozen model uses `Age` (its largest magnitude coefficient) and `MaritalStatus` as inputs, both protected bases under ECOA/Regulation B. Anything that touches training is an opportunity to reduce that exposure — and equally an opportunity to make it worse without noticing.

## Decision

**The model stays frozen by default. It changes only through an explicit propose → approve → re-export → re-validate gate, and never as a side effect of implementation work.**

The gate, in order:

1. **Propose in writing before changing anything.** State what would change (features, training data, algorithm, hyperparameters, preprocessing), what improvement is expected, and what it costs — specifically which already-settled decisions it invalidates.
2. **Wait for Panth's approval.** No model, preprocessing, or training-data change is made without it. This is a hard stop, not a courtesy notification.
   *Enforced mechanically, not on trust:* `.claude/settings.json` denies `Edit`/`Write` on `app.py`, `model_params.json`, `**/*.pkl`, and `data/**`, so an agent cannot edit a frozen artifact or the training data even if it overlooks this ADR. `export_model_params.py` stays editable and still regenerates `model_params.json` when run, because it writes through the shell rather than a file-editing tool — the sanctioned path is unaffected. That is also the limit of the enforcement: a shell command can still write to a protected path, so the rule raises the cost of an accidental change, it does not make one impossible. The gate above is still the actual policy.
3. **Re-export, don't hand-edit.** `export_model_params.py` regenerates `model_params.json` from the training data — coefficients, scaler statistics, encoder categories, outlier bounds, credit-score band breakpoints. Anything derived from data must come from that script so a change propagates by re-running it. Never patch a constant in `model_params.json` or hardcode one in the Worker.
4. **Re-validate parity.** The script's scaler-parity assertion must pass, and the TypeScript
   pipeline's numerical parity against `predict_proba` ([[TEST_STRATEGY]]) must be re-run. A model change that breaks parity is not done.
5. **Re-measure, then re-record.** Re-run the measurements behind [[0007-approval-decision-and-suggestions]] and update that ADR's Evidence section with the new
   numbers. If a conclusion flips — for instance if a retrain makes extending the loan term genuinely helpful — the parameters change with it rather than the evidence being left stale.
6. **Re-check the protected-feature position.** Confirm which protected or proxy features the new model uses and with what weight, and update [[0005-ml-model-hosting]]'s compliance flag and the filter list. A retrain is the one point at which dropping `Age` and `MaritalStatus` from the model's inputs entirely becomes possible — worth proposing on its own merits, since a model that never sees them cannot have them filtered out of its explanation as an afterthought.

## What "prepare for that" means concretely

Adding training data shifts every data-derived constant: scaler means and scales, one-hot categories (a new dataset may contain an `EmploymentType` this one lacks), IQR outlier bounds, `CreditScore` quintiles, and the coefficients themselves. The preparation is therefore not abstraction, it is discipline about where constants live:

- **One source.** `model_params.json` is the only place runtime constants come from, and
  `export_model_params.py` is the only thing that writes it. Already true as of this ADR.
- **Derived, not hardcoded.** The credit-score band breakpoints are exported as data-derived quintiles rather than written into the rate card, precisely so a dataset addition re-bands the population automatically. The APR per band stays policy in
  [[0007-approval-decision-and-suggestions]].
- **Schema read, not assumed.** Stage 1's TypeScript must read `feature_order`,
  `categorical_columns`, and `numeric_features` from the JSON rather than embedding a 26-feature list, so a feature-count change surfaces as a data change instead of a code rewrite.
- **Unknown categories must fail loudly.** The existing encoder was fitted with
  `handle_unknown='ignore'`, which maps an unseen category to all-zeros — silently identical to the dropped reference category. That is tolerable while the category set is fixed and known; it becomes a correctness trap the moment new data widens it. Stage 1 validates the applicant's category against `all_categories` and rejects unknown values rather than scoring them as the
  reference level.

## Options Considered

### Option A: Frozen by default, changes through an explicit approval gate
**Selected.** Keeps the AI layer's scope intact and its measured decisions trustworthy, while
leaving a real path to improving the model. The cost is process: every model change carries a re-export, a parity re-run, and an evidence refresh.

**Pros:** Settled decisions stay honest, because anything that invalidates them forces them to be revisited. Panth keeps the call on risk-bearing changes. Dataset expansion becomes a re-run rather than a rewrite.
**Cons:** Slower than changing the model opportunistically mid-implementation — which is the point.

### Option B: Keep the model permanently frozen (the original PRD position)
**Pros:** Simplest; every measurement stays valid indefinitely.
**Cons:** Contradicts what Panth actually wants, and permanently locks in a model whose strongest predictor is a protected basis. Rejected as no longer accurate to the project's goals.

### Option C: Treat the model as freely modifiable during implementation
**Pros:** Fastest iteration on model quality.
**Cons:** Every number in [[0007-approval-decision-and-suggestions]] would drift out of date without anyone noticing, the eval suite's fixed expected values would need constant regeneration, and compliance exposure would change without review. Rejected — this is exactly the failure mode the gate exists to prevent.

## Consequences

- Enforcement lives in `.claude/settings.json` (`permissions.deny`), committed at project scope so it applies to everyone working in this repo rather than only to whoever configured it. A native permission rule was chosen over a `PreToolUse` hook because it needs no script, no `jq`/Python dependency, and cannot be defeated by a hook-execution failure. Verified by probe: all four patterns blocked, `CLAUDE.md` and `export_model_params.py` still editable, `export_model_params.py` still runs and reproduces `model_params.json` byte-identically.

- [[PRD]] §3's out-of-scope list is narrowed: model retraining is no longer excluded outright, it is gated. The AI layer's scope is unchanged.
- [[AI_SDLC_CHECKLIST]] Phases 2 and 4 (data labeling, splitting, training, hyperparameter tuning) are marked N/A on the grounds that no training happens in this project. That reasoning holds only while the model stays frozen — an approved retrain reactivates those phases for the scope of that change, and they should be worked through rather than inherited as N/A.
- [[TEST_STRATEGY]] gains a standing requirement: the parity test and the fixed eval set's expected attribution values are tied to a specific model export, so both are regenerated as part of steps 4 and 5 of the gate rather than treated as stable fixtures.
- Any dataset added must be recorded — source, licence, row count, and whether its schema matches the existing 26-feature pipeline. A dataset that introduces or drops a feature is a model change, not a data top-up, and goes through the full gate.
- This ADR governs the model. It does not gate ordinary AI-layer implementation work (prompts, retrieval, portal, evals), which proceeds normally per [[IMPLEMENTATION_PLAN]].

## Action Items
1. [ ] Record each added dataset's source, licence, row count, and schema compatibility before using it for anything.
2. [ ] When a retrain is first proposed, explicitly evaluate dropping `Age` and `MaritalStatus` from the model's inputs, and record the accuracy cost of doing so in [[0005-ml-model-hosting]].
3. [ ] Add the unknown-category rejection described above to Stage 1's input validation, alongside the `outlier_bounds` clamp.

## Related

[[Home]] · [[PRD]] · [[AI_SDLC_CHECKLIST]] · [[0005-ml-model-hosting]] · [[0007-approval-decision-and-suggestions]] · [[TEST_STRATEGY]] · [[IMPLEMENTATION_PLAN]]
