---
title: "ADR-0007: Approval Decision, Pricing & Counterfactual Suggestions"
status: Accepted (architecture) — parameters proposed, pending confirmation
tags: [adr, decision]
date: 2026-09-03
---

# ADR-0007: Approval Decision, Pricing & Counterfactual Suggestions

**Status:** Architecture Accepted; specific numeric parameters below are proposed defaults, not yet confirmed.
**Date:** 2026-09-03
**Deciders:** Panth

## Context

The intended user flow: an applicant fills out a full form (profile + desired loan), the system decides approve/deny, and if approved, states an interest rate and loan term; if denied, gives a reason and a "might help" suggestion.

Two problems, both confirmed empirically against the actual model (`model_params.json`), not assumed:

1. `InterestRate` and `LoanTerm` are **inputs** the frozen model was trained to score against, not outputs it produces. There is no "what rate should we offer" logic anywhere in the existing repo — this is new decision logic, not something to extract from the pickle files.
2. The obvious design — raise the offered rate for riskier applicants to price in the risk — makes this specific model's predicted default probability *worse*, not better. A sweep at a fixed applicant profile: `P(default)` rises from 0.333 at 4% APR to 0.603 at 20% APR, monotonically. The model reads rate as a marker of risk (from whatever process generated the training data's historical rates), not a dial that offsets it. Loan term has a comparatively negligible effect (~1 point of `P(default)` across the full 12–60 month range).

## Decision

**Rate is assigned by a simple, transparent, deterministic rate card (credit-score band × requested term) — never searched for via the model.** The model's only job is to gate approve/deny at that assigned rate, for the applicant's requested amount and term. No upward rate search, because the evidence above shows it never helps on this model — the lowest rate the card allows is also always the applicant's best chance of approval.

**Approval threshold:** `P(default) ≤ 0.50` (sklearn's own default decision boundary) is the proposed starting point — approve at the assigned rate if under it, deny if over. This is a risk-appetite choice, not a derived fact; happy to move it if you want to be more conservative or more permissive.

**On denial, suggestions are computed, not guessed by the LLM.** For an explicit allow-list of features, compute the minimum single-feature change (holding everything else fixed) that would flip `P(default)` below the threshold, and surface the 1–2 most feasible ones. The LLM's only job is phrasing them with appropriate hedging ("might help," "estimated, not guaranteed") — the number itself is exact linear-model math, same as the explanation layer.

**Allow-listed suggestion features:** requested `LoanAmount` (reduce), requested `LoanTerm` (extend), `HasCoSigner` (add one), `CreditScore` (directional target, phrased as an estimate). **Never** `Age`, `MaritalStatus`, `EmploymentType`, or `Education` — confirmed via the same sweep that `Age` alone swings `P(default)` from 0.558 (age 22) to 0.161 (age 70), by far the model's most powerful lever. That's exactly why it's the one lever this system will never mention, regardless of how "helpful" it would mathematically be to suggest.

## Proposed default parameters (confirm or override)

**Rate card** (illustrative starting point — a real version belongs in the RAG policy corpus, see Consequences):

| CreditScore | 12–36mo APR | 48–60mo APR |
|---|---|---|
| 750+ | 6.5% | 7.0% |
| 700–749 | 8.0% | 8.5% |
| 650–699 | 10.5% | 11.0% |
| 600–649 | 13.0% | 13.5% |
| <600 | 16.0% | 16.5% |

**Term options offered:** 12, 24, 36, 48, 60 months (applicant picks one as part of the request; displayed to them in years where that reads better, e.g. "5 years").

**Approval threshold:** `P(default) ≤ 0.50`.

## Consequences

- Stage 1 (`docs/IMPLEMENTATION_PLAN.md`) expands from "explain a given decision" to "assign a rate via the rate card → score the model → decide approve/deny → explain, and on denial, compute suggestions." All of this is still plain arithmetic in the Worker — no new hosting/architecture implications beyond what ADR-0005 already established.
- The rate card is itself a policy document — a natural fit for the Stage 2 RAG corpus, so the explanation can cite "why this rate" from the same retrieval mechanism that grounds the denial reasons.
- This reintroduces the counterfactual/"what-if" capability that was explicitly deferred earlier in scoping — worth naming plainly rather than pretending it's unrelated. It's scoped down from a free-form agent tool to a fixed, pre-computed suggestion on the denial path, with a hard-coded feature allow-list, which is a meaningfully smaller and safer surface than the original open-ended version.
- `docs/TEST_STRATEGY.md` needs a new check: suggestions must only ever reference allow-listed features, with the same 100%-hard-gate treatment as the protected-feature exclusion check on explanations.

## Action Items
1. [ ] Confirm or adjust the rate card, term options, and 0.50 threshold above.
2. [ ] Implement the rate-card lookup, scoring, and suggestion-computation logic in Stage 1 per `docs/IMPLEMENTATION_PLAN.md`.
3. [ ] Add the rate card as a citable document in the Stage 2 policy corpus.
4. [ ] Add the suggestion allow-list enforcement test to `docs/TEST_STRATEGY.md`'s hard-gate checks.

## Related

[[Home]] · [[PRD]] · [[0005-ml-model-hosting]] · [[TEST_STRATEGY]] · [[IMPLEMENTATION_PLAN]]
