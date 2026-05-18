## Summary

<!-- One or two sentences. What changed and why. -->

## Linked issue

Closes #<N> (see `.github/ISSUES.md`).

## Scope

- [ ] Code
- [ ] Tests
- [ ] Docs / research notes
- [ ] Notebook

## Verification

- [ ] `pytest` passes locally
- [ ] If touching a solver: parity check vs the other solver on shared instances
- [ ] If touching the notebook: `jupyter nbconvert --execute` succeeds

## Reviewer checklist

- [ ] Subject matches scope (no unrelated changes piggy-backed)
- [ ] Tests cover the new behavior
- [ ] Docs / research notes updated when behavior or theory changes
- [ ] Acceptance criteria from the issue are met
