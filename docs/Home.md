---
title: Loan Default AI Layer — Vault Home
tags: [moc, project]
date: 2026-09-03
---

# Loan Default Prediction — AI Engineering Layer

Map of contents for this project's documentation vault. This vault **is** `docs/` in the project repo — keep it there so docs stay versioned with the code (see [[0004-deployment-platform]] for why "single source of truth" matters here).

## Start here

- [[PRD]] — problem, scope, non-goals, success criteria, open decisions
- [[AI_SDLC_CHECKLIST]] — the user-supplied AI-SDLC checklist mapped phase-by-phase onto this actual project
- [[TEST_STRATEGY]] — eval/test plan across all four build stages
- [[IMPLEMENTATION_PLAN]] — the staged build plan (TypeScript/Workers), what Claude Code actually follows once ADR-0005 is Accepted

## Handing this off to Claude Code

`CLAUDE.md` at the **repo root** (a sibling of this `docs/` vault, not inside it) is the actual agent bootstrap file — it's what Claude Code auto-reads at the start of a session, and it points here using plain file paths rather than `[[wikilinks]]` (Claude Code won't resolve Obsidian's link syntax). This vault is the source of truth Claude Code is instructed to read and update; it isn't a substitute for that file, and that file isn't a substitute for keeping these notes current.

## Architecture Decision Records

Status at a glance — update the `status` frontmatter field on each note as decisions land (a Dataview query below will auto-list them once the Dataview plugin is installed).

- [[0001-llm-provider]] — Accepted — Gemini API
- [[0002-vector-store]] — Accepted — Cloudflare Vectorize
- [[0003-observability]] — Accepted — Cloudflare AI Gateway + D1
- [[0004-deployment-platform]] — Accepted — Cloudflare Workers + Wrangler + GitHub Actions
- [[0005-ml-model-hosting]] — Accepted — model confirmed as `LogisticRegression`, exact attribution as plain arithmetic in the Worker
- [[0006-frontend-framework-hosting]] — Accepted — SvelteKit applicant-facing portal on Cloudflare
- [[0007-approval-decision-and-suggestions]] — Architecture Accepted, parameters pending confirmation — rate-card approval gate + hard-coded suggestion allow-list

## Live ADR status (requires the free Dataview plugin)

```dataview
table status, date
from "adr"
sort file.name asc
```

## Recommended free Obsidian plugins (optional, current-demand tooling)

- **Dataview** — query notes like a database; powers the table above and can later track eval-run history if you log results as notes.
- **Templater** — scaffold new ADRs from a template (keeps the format above consistent as you add more decisions).
- No sync plugin needed here since the vault lives inside the git repo — plain `git commit` covers versioning; skip Obsidian Git unless you deliberately choose the separate-vault option later.

Enable via Settings → Community plugins → Browse (Community Plugins must be turned on; Obsidian's core is free for personal use).

## Project process note

Phases 2 and 4 of the source checklist (data labeling, model training, hyperparameter tuning) are marked N/A in [[AI_SDLC_CHECKLIST]] — this project integrates pretrained models around an already-trained, frozen classifier, it doesn't train one. See that note for the full reasoning, not just the verdict.
