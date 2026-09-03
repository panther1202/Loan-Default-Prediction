# .claude/ — Claude Code project config

This folder is for Claude Code *mechanics* only: slash commands, and later (only if a real need shows up) hooks or settings. It is deliberately **not** a copy of the larger `.claude` structure you might have seen on other projects (`architecture/`, `context/`, `rules/`, `skills/`, `scripts/`, a permission system).

That structure exists on a live, multi-contributor product because real, accumulated friction earned it. This project doesn't have that friction yet, and copying the shape wouldn't give you the substance — it would just give you folders to keep in sync.

**This project's knowledge already lives elsewhere — don't duplicate it here:**
- Decisions, architecture, scope, and process → `docs/` (the Obsidian vault: `PRD.md`, `docs/adr/*`, `TEST_STRATEGY.md`, `IMPLEMENTATION_PLAN.md`, `AI_SDLC_CHECKLIST.md`).
- Agent bootstrap instructions → `CLAUDE.md` at the repo root (not inside this folder — that's Claude Code's standard auto-load location, and it stays there).

If you're ever tempted to add a `context/` or `architecture/` folder here: don't. Update the vault instead. Two places claiming to be the source of truth for the same decision is exactly the kind of drift that already caused real bugs in this project (`CLAUDE.md` citing a stale ADR count more than once).

## What's actually here, and why

- `commands/new-adr.md` — scaffolds the next ADR in `docs/adr/`, matching the project's established format exactly. Justified by an already-demonstrated need: seven ADRs have been hand-written so far.
- `commands/doc-check.md` — audits `CLAUDE.md` and the vault for stale ADR counts, broken `[[wikilinks]]`, and status mismatches. Justified by an already-demonstrated bug: this exact class of drift has happened twice.

Add anything else — a rule file, a hook, a project skill — only once a specific, repeated piece of friction justifies it. Not speculatively, not because a bigger project has one.
