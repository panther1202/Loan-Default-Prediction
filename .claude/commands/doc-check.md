---
description: Audit CLAUDE.md and the docs vault for stale ADR counts, broken wikilinks, and status mismatches
---

Audit this project's documentation for the specific kind of drift that has already happened more than once in this project's history. Report findings before changing anything — some mismatches may be intentional (e.g. an ADR deliberately left at "Proposed").

1. **ADR range staleness:** read `CLAUDE.md`, find every place it states or implies how many ADRs exist (e.g. "0001 through 0008" — read the actual count from the folder, do not trust this example), and confirm it matches the actual files in `docs/adr/`.
2. **Broken wikilinks:** scan every `.md` file under `docs/` for `[[wikilink]]` references (including piped links like `[[target|display text]]`), and confirm each target actually exists as a file in `docs/` (matched by filename, without extension, case-sensitive).
3. **Status mismatches:** for each file in `docs/adr/`, read its `status` frontmatter field, and confirm `docs/Home.md`'s ADR list describes the same status.
4. **Orphaned ADRs:** confirm every file in `docs/adr/` is linked from at least `docs/Home.md`.

Report every mismatch found, with the specific file and what's wrong. Do not edit anything yet — ask before fixing, since the right fix (update the stale reference vs. the reference was actually correct and something else drifted) isn't always obvious from the mismatch alone.
