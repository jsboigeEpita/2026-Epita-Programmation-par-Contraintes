# Issues ledger

In-repo issue tracker. Source of truth for the planning trail. Each
entry mirrors either a real PR (with merge commit) or a self-contained
direct commit on `main`.

Lifecycle: planning commit `docs(plan): open issue #N` adds the entry;
closing commit `docs(plan): close issue #N` flips the Status line. PRs
reference issue numbers in their merge messages.

## #1 — Synthetic instance generator (random + regions)
- **Owner:** @NCH04
- **Reviewer:** @Sosolalt
- **Branch:** feat/generator
- **Status:** closed 2026-04-28 by merge of PR #1, reviewed by @Sosolalt
- **Acceptance:**
  - [x] random + regions distributions
  - [x] reproducible by seed
- **Discussion:**
  - @NCH04: small/med/large/stress sizes
  - @Sosolalt (review): outputs reproducible by seed
