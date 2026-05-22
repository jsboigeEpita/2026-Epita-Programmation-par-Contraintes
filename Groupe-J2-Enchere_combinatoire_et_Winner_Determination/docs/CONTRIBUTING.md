# Contributing — J2 Combinatorial Auctions / WDP

Working agreement for the 3-person team. Mirrors `PROJECT_TRACKER.md`
and [`.github/ISSUES.md`](../.github/ISSUES.md).

## Branching

- `main` — integration branch. Merges via `git merge --no-ff` to
  preserve PR topology.
- `feat/<slug>` — feature branches (one per non-trivial issue).
- `fix/<slug>` — hotfixes.
- `docs/<slug>` — documentation-only changes.

Trivial single-file docs/chore changes may go directly on `main`. Core
solver and VCG work was committed directly to `main` by the tech lead;
non-trivial contributions from the other two members went through the
PR flow.

## Issue lifecycle

1. **Define** — append an entry in
   [`.github/ISSUES.md`](../.github/ISSUES.md) with owner, reviewer,
   acceptance criteria, target branch. Commit with
   `docs(plan): open issue #N — <title>`.
2. **Work** — atomic commits on the feature branch (or directly on
   `main` for small scoped work).
3. **Review** — open PR. Assigned reviewer reviews. On approval, the
   reviewer performs the merge — the merge commit's **committer** is
   the reviewer, **author** is the owner, and the message carries a
   `Reviewed-by:` trailer.
4. **Close** — merge commit lands on `main`. Follow-up
   `docs(plan): close issue #N` flips the ledger Status line.

## Commit messages (Conventional Commits)

Format: `<type>(<scope>): <subject>` — imperative, ≤ 60 chars.

Types: `feat`, `fix`, `docs`, `test`, `refactor`, `perf`, `chore`,
`build`, `ci`, `style`, `revert`.

Scopes for project-management commits:
- `docs(plan): open issue #N — <title>` / `docs(plan): close issue #N`

Examples:
```
docs(plan): open issue #1 — synthetic instance generator
feat(cpsat): baseline set-packing model
fix(vcg): leave-one-out welfare cache invalidation
```

Merge commit (committer = reviewer):
```
Merge PR #1: synthetic instance generator

Closes #1
Reviewed-by: Sosolalt <lucas.majerczyk@epita.fr>
```

Template at [`.gitmessage`](../.gitmessage).

## Code style

- Python ≥ 3.11, type hints encouraged on public APIs.
- `pytest` for tests, kept under `tests/`.
- Notebooks built via `scripts/build_notebook.py` for reproducibility —
  do not hand-edit the `.ipynb` directly.

## Review checklist (reviewer)

- [ ] Subject of the commit / PR matches scope.
- [ ] Tests cover the new behavior.
- [ ] No unrelated changes piggy-backed.
- [ ] Docs / research notes updated when behavior or theory changes.
- [ ] If touching a solver, parity check with the other solver on
      shared instances.
