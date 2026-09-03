---
title: "ADR-0009: Training Data Source & LendingClub Evaluation"
status: Accepted
tags: [adr, decision]
date: 2026-09-03
---

# ADR-0009: Training Data Source & LendingClub Evaluation

**Status:** Accepted — for the sequencing decision below. Adopting LendingClub is **not** approved; it
remains a proposal subject to [[0008-model-change-policy]]'s gate.
**Date:** 2026-09-03
**Deciders:** Panth

## Context

[[0008-model-change-policy]] anticipated additional training datasets and required each to be assessed before use. Panth put forward six Kaggle candidates, all LendingClub:

1. `wordsforthewise/lending-club` · 2. `ethon0426/lending-club-20072020q1` ·
3. `jeandedieunyandwi/lending-club-dataset` · 4. `janiobachmann/lending-club-first-dataset` ·
5. `adarshsng/lending-club-loan-data-csv` · 6. `husainsb/lendingclub-issued-loans`

Assessing them turned up a fact about the *existing* data that matters more than the candidates do, so both are recorded here.

## Evidence

### 1. The current training data is synthetic

Measured over all 255,347 rows of `data/Loan_default.csv`:

| Column | min | max | mean | skew | distinct |
|---|---|---|---|---|---|
| `Age` | 18 | 69 | 43.5 | 0.001 | 52 |
| `Income` | 15,000 | 149,999 | 82,499 | −0.000 | 114,620 |
| `LoanAmount` | 5,000 | 249,999 | 127,579 | −0.002 | 158,729 |
| `CreditScore` | 300 | 849 | 574.3 | 0.005 | 550 |
| `MonthsEmployed` | 0 | 119 | 59.5 | −0.002 | 120 |
| `NumCreditLines` | 1 | 4 | 2.5 | −0.000 | 4 |
| `InterestRate` | 2.0 | 25.0 | 13.5 | 0.005 | 2,301 |
| `DTIRatio` | 0.1 | 0.9 | 0.5 | −0.001 | 81 |

Skew is ≈ 0.000 on every numeric column, bounds sit on round numbers, and `Income` deciles are evenly spaced about 13,500 apart. Real income is log-normal with skew of roughly 2–5. These are uniform random draws, not observed borrowers. Default rate is 11.61%.

This retro-explains three things previously logged as model quirks:

- **Zero IQR outliers** across all nine numeric columns ([[0005-ml-model-hosting]]) — uniform
  distributions have none by construction, so the outlier clamp was always a no-op.
- **`CreditScore` is a top-3 attribution in only 0.8% of denials**
  ([[0007-approval-decision-and-suggestions]] Evidence 1) — there is no credit-score-to-default relationship in the data to learn.
- **`EstimatedEMI` carries a negative coefficient** (Evidence 3), making a larger monthly payment *lower* predicted default. Not a subtle economic effect; an artifact of uncorrelated noise.

The model is a correctly-fitted logistic regression over data with no real signal. It is entirely
adequate as a fixed decision function for an AI-engineering project to explain, and it is not a credit model in any meaningful sense.

### 2. LendingClub cannot extend this schema

From LendingClub's published data dictionary (151 columns), mapped against the 16 raw columns our pipeline consumes:

| Our column | LendingClub |
|---|---|
| `Age` | **absent** — never published, it is a protected basis |
| `MaritalStatus` | **absent** |
| `Education` | **absent** |
| `HasDependents` | **absent** |
| `HasCoSigner` | **absent** — nearest is `application_type` (INDIVIDUAL/JOINT) with `annual_inc_joint` |
| `CreditScore` | `fico_range_low` / `fico_range_high` |
| `Income` | `annual_inc` |
| `LoanAmount` | `loan_amnt` |
| `InterestRate` | `int_rate` |
| `DTIRatio` | `dti` — a 0–100 percentage, ours is a 0.1–0.9 ratio |
| `MonthsEmployed` | `emp_length` — banded 0–10 years, not months |
| `NumCreditLines` | `open_acc` / `total_acc` |
| `HasMortgage` | `home_ownership` or `mort_acc` |
| `LoanPurpose` | `purpose` |
| `LoanTerm` | `term` — **only 36 and 60**, not the 12/24/36/48/60 menu in [[0007-approval-decision-and-suggestions]] |
| `Default` | `loan_status` — needs filtering to matured loans or it carries survivorship bias |

Five of sixteen features are simply not collected, and the term menu collapses from five options to two. Per [[0008-model-change-policy]], "a dataset that introduces or drops a feature is a model change, not a data top-up." Every candidate here is the second kind.

### 3. The six candidates are one dataset

All six are the same LendingClub release at different vintages and cleaning levels, so the schema verdict above applies identically to each. They are also **not additive to one another** — combining overlapping extracts from a single source duplicates rows.

| # | Dataset | Assessment |
|---|---|---|
| 1 | `wordsforthewise/lending-club` | Canonical: accepted 2007–2018Q4, all 151 columns, plus a separate rejected-loans file. The only one worth taking. |
| 2 | `ethon0426/lending-club-20072020q1` | Same data through 2020Q1. Fair alternative if the extra vintages matter. |
| 3 | `adarshsng/lending-club-loan-data-csv` | 2007–2015 subset of the same source. Strictly less. |
| 4–6 | `jeandedieunyandwi`, `janiobachmann`, `husainsb` | Pre-cleaned tutorial cuts. Actively unsuitable: they drop columns and bake in another author's imputation and feature choices, in a project whose stated standard is preprocessing that can be verified and re-exported. |

Per-dataset row counts are unverified — Kaggle renders its dataset pages client-side and could not be read directly. That does not affect the conclusion, which rests on the LendingClub schema rather than on any one extract's size.

## Decision

**Keep `data/Loan_default.csv` as the training data for Stages 1–5. Do not add any of the six candidates to it. Treat a LendingClub swap as a separate, later, gated proposal, revisited once Stage 1 is demoable.**

Stage 1's pipeline reads its schema from `model_params.json` rather than hardcoding it
([[0008-model-change-policy]]), so it is indifferent to whether the underlying numbers are real. The explainability, filtering, rate-card, and eval work all stand on their own; none of it needs a better model underneath to be built or demonstrated.

## Options Considered

### Option A: Keep the current dataset, build Stage 1, revisit the swap afterwards
**Selected.**

**Pros:** Unblocks Stage 1 immediately. Preserves every measured parameter in
[[0007-approval-decision-and-suggestions]]. Keeps the swap decision available rather than foreclosed, and defers it until there is a working pipeline to evaluate it against.
**Cons:** The model being explained has no real predictive signal. Acceptable because the project's subject is the AI layer, not the classifier — but it must be stated plainly rather than glossed
(see Consequences).

### Option B: Swap to LendingClub now, before Stage 1
**Pros:** Real borrowers, real outcomes, and a genuine compliance win — LendingClub publishes neither age nor marital status, so a model trained on it *cannot* use them. The protected-feature filter would stop being the load-bearing safeguard it currently is.
**Cons:** Blocks Stage 1 behind a full retrain. Invalidates the entire Evidence section of
[[0007-approval-decision-and-suggestions]] before that ADR has ever been implemented. And it carries its own trap: `int_rate` is the rate *LendingClub's own grading model assigned*, so training on it rebuilds exactly the circularity Evidence 1 of that ADR was written to remove. Rejected on sequencing, not on merit.

### Option C: Add LendingClub alongside the current data
**Pros:** None that survive inspection.
**Cons:** Requires inventing `Age`, `MaritalStatus`, `Education`, `HasDependents`, and `HasCoSigner` for every LendingClub row. Imputing five absent features across millions of rows is fabricating training data, and fabricating a *protected* attribute is worse than fabricating an ordinary one. Rejected outright.

## Trade-off Analysis

Option B is the better destination and Option A is the better next step; they are not in conflict. The deciding factor is that nothing in Stages 1–5 is blocked by the data being synthetic, while everything in Stage 1 is blocked by a retrain in flight. Doing the swap later also means evaluating it against a working pipeline and a passing eval suite, instead of guessing at its effects.

Option C is the only genuinely wrong answer, and it is the one that looks most like "adding more training data" from the outside — which is why it is written down rather than quietly skipped.

## Consequences

- Stage 1 proceeds against `model_params.json` as planned. No change to
  [[IMPLEMENTATION_PLAN]] or [[0007-approval-decision-and-suggestions]]'s parameters.
- **[[0007-approval-decision-and-suggestions]]'s Evidence section describes a synthetic population.** Its numbers are correct measurements of this model on this data, and they are the right basis for the current build. They are not findings about lending. Anyone reading them as consumer-credit insight is reading them wrong.
- The protected-feature filter from [[0005-ml-model-hosting]] stays load-bearing (`Age` in the top-3 of 76% of denials) for as long as this dataset is in use.
- No candidate dataset is downloaded or committed under this ADR. `data/` remains write-protected per [[0008-model-change-policy]].
- If the swap is later approved, it goes through that ADR's full gate and supersedes this decision; the `int_rate` circularity and the matured-loans filter are the two traps to design around before any retraining starts.
- The synthetic finding is worth surfacing in any demo of this project. "The classifier is a
  stand-in; here is how the AI layer around it is built and verified" is a stronger and more honest claim than implying the decisions are real credit decisions.

## Action Items
1. [ ] Do not download or commit any of the six candidate datasets while this ADR stands.
2. [ ] Revisit after Stage 1 is demoable: if the swap is proposed, use candidate 1 (`wordsforthewise/lending-club`) and record its source, licence, row count, and schema
   compatibility per [[0008-model-change-policy]] Action Item 1 before any other work.
3. [ ] If that proposal is made, decide `int_rate` handling explicitly — excluded, or included with the circularity documented — and re-measure every number in [[0007-approval-decision-and-suggestions]]'s Evidence section against the new model.
4. [ ] Note the synthetic-data caveat wherever this project is demoed or written up, alongside the existing "learning simulation" disclaimer.

## Related

[[Home]] · [[PRD]] · [[0005-ml-model-hosting]] · [[0007-approval-decision-and-suggestions]] · [[0008-model-change-policy]] · [[TEST_STRATEGY]] · [[IMPLEMENTATION_PLAN]]
