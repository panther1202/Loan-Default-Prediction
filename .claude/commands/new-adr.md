---
description: Scaffold a new ADR in docs/adr/ using this project's established format
argument-hint: <short title for the decision>
---

Create a new Architecture Decision Record for this project, for the decision: $ARGUMENTS

Steps:
1. List `docs/adr/` and find the highest existing ADR number (currently up to 0007). Use the next number, zero-padded to 4 digits.
2. Read `docs/adr/0005-ml-model-hosting.md` as the template — match its exact frontmatter shape (`title`, `status`, `tags: [adr, decision]`, `date`) and its exact section structure (`## Context`, `## Decision`, `## Options Considered`, `## Trade-off Analysis`, `## Consequences`, `## Action Items`, `## Related`).
3. Create `docs/adr/000N-<slug>.md` (slug: lowercase, hyphenated, from the argument) with that structure filled in for the decision at hand. Set `status: Proposed` unless the user explicitly says to mark it Accepted — ADRs in this project don't get accepted silently, that's always a call for Panth to confirm, same as every prior one.
4. Add the new ADR to the list in `docs/Home.md` (same format as the existing entries) and to the `## Related` line in `docs/PRD.md`.
5. Update `CLAUDE.md`'s note about the ADR range (search for "0001 through") so it reflects the new highest number.
6. Report back a summary of what was created and updated — don't silently assume this is complete without saying so.

Do not invent the content of Context/Decision/Options if the user's argument doesn't give enough detail — ask what's missing rather than filling it with a plausible-sounding guess.
