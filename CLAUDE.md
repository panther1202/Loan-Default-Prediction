# CLAUDE.md

Read this before writing any code in this repo.

## What this repo is

Two layers: (1) an existing, already-trained, **frozen** ML loan-default model — do not retrain it or change its core logic as part of this work; (2) an AI-engineering layer being added on top of it. Layer 2 is documented in `docs/`, which is an Obsidian vault. The `[[wikilink]]` syntax you'll see in those notes is Obsidian-only and will not resolve for you — open files by their plain path (e.g. `docs/adr/0005-ml-model-hosting.md`), not by the bracketed name.

## Before writing any code

1. Read, in this order: `docs/PRD.md` → `docs/AI_SDLC_CHECKLIST.md` → every file in `docs/adr/` (currently 0001 through 0007 — check the folder, this number will keep growing) → `docs/TEST_STRATEGY.md` → `docs/IMPLEMENTATION_PLAN.md`.
2. `docs/adr/0005-ml-model-hosting.md` is Accepted: the model is confirmed `sklearn.LogisticRegression` (26 features), and its exact parameters are already exported to `model_params.json` at the repo root. Stage 1 works from that JSON directly — see `docs/IMPLEMENTATION_PLAN.md` for the exact preprocessing/scoring pipeline. That ADR also carries a compliance flag worth reading before touching Stage 1: `Age` is the model's single strongest predictor and, along with marital status, a protected basis under ECOA — both must be filtered out of any LLM-facing explanation, never just trusted to the prompt. If you hit a *new* architectural fork not already covered by an ADR, resolve it the same way this one was resolved: inspect the actual repo, update or add the ADR with your finding and reasoning, don't decide it silently in code comments.
3. The stack is fixed by `docs/adr/0004-deployment-platform.md`: **TypeScript on Cloudflare Workers**, not Python. If a plan or an old note pushes you toward a Python web framework or a `google-genai` Python import for this new layer, that's stale — the ADRs are the current source of truth, not any earlier draft.
4. There's a proper applicant-facing portal in scope (`docs/adr/0006-frontend-framework-hosting.md`: SvelteKit, Cloudflare-hosted, Stage 5 in `docs/IMPLEMENTATION_PLAN.md`). It's a fresh application form, not a lookup of an existing record. Its visual/UX design is being handled by the user directly, outside this repo's docs — don't design screens here, but do build to whatever design artifact they hand you. Two things from that ADR are non-negotiable regardless of visual design: the "learning simulation" disclaimer must render on every explanation view, and this stage doesn't start until Stage 4's eval suite is passing at 100% on the fixed set, because the portal removes the human-review step that used to sit between the LLM's output and the applicant.
5. `docs/adr/0007-approval-decision-and-suggestions.md` covers the approve/deny threshold and rate-card logic — the decision rule is `P(default) ≤ 0.50 → approve`, `P(default) > 0.50 → deny` (a risk score, not a creditworthiness score — don't flip this). Its specific numbers (rate card, term list, exact threshold) are still pending final confirmation from Panth as of this writing — check the ADR's status line before hardcoding them.
6. **Before starting Stage 2 (RAG grounding) implementation, stop and discuss the design at length with Panth first — do not build from `docs/IMPLEMENTATION_PLAN.md`'s Stage 2 section alone.** That section is marked as a placeholder sketch, not an approved design, the same way Stage 1's original three-option ADR-0005 sketch wasn't a design until the repo access discussion resolved it. Open questions that need discussion before code: what actually goes in the policy corpus, how the ADR-0007 rate card factors in as a citable document, chunking strategy, and retrieval-failure behavior. This applies to Stage 2 specifically because it's flagged here — don't assume every future stage needs the same pre-discussion gate unless it's marked that way too.

## While implementing

- Follow `docs/IMPLEMENTATION_PLAN.md`'s stage order: explainability → RAG → agent → evals. Each stage should be independently runnable and demoed before the next one starts. Don't jump ahead because a later stage looks easy.
- Every Gemini call goes through Cloudflare AI Gateway (`docs/adr/0003-observability.md`) starting in Stage 1 — this is not something to retrofit in Stage 4.
- If an implementation decision deviates from what an ADR says, update that ADR rather than quietly diverging from it. Same rule as step 2 above, for the whole project's lifetime, not just ADR-0005.
- Before calling a stage "done," check it against the relevant phase in `docs/AI_SDLC_CHECKLIST.md` and the coverage targets in `docs/TEST_STRATEGY.md` — not just "it runs."

## Ground rules

- Never assume the model's feature schema, serving setup, or serialization format — verify it from the actual repo contents.
- Every place adverse-action-notice-style content is generated or documented, note clearly that this is a learning simulation, not reviewed legal/compliance language.
- If you're about to make an architectural choice that isn't already covered by an existing ADR, write a new one (`docs/adr/000N-title.md`, same format as the existing ones) instead of deciding it inline and moving on.
