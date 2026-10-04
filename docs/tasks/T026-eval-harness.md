# T026: Eval harness, scorers and splits

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol in `AGENTS.md`.

| | |
|---|---|
| Milestone | M2: Data and evals (branch `milestone/M2`) |
| Depends on | T021, T023, T024, T025 |
| Read first | EVALS §3–6; LIBRARY_NOTES inspect-ai |
| Allowed to modify | `evals/**`, `tests/evals/**`, `Makefile`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Sealed paths (see AGENTS.md), other tasks' entries, existing tests' assertions |

## Goal
inspect-ai tasks, deterministic scorers, lineage-aware splits and the sealed test.

## Acceptance criteria
- [ ] AC1: inspect-ai tasks per deliverable kind and suite; `make eval SUITE=<name>` works
- [ ] AC2: Deterministic scorers from EVALS §3
- [ ] AC3: Splits by deal lineage: train/dev/selection_holdout; sealed test generated only when `EVAL_SEALED_SEED` is set (CI)
- [ ] AC4: Reports written to `evals/reports/`
- [ ] AC5: Without keys, suites run against FakeRunner placeholders and score the plumbing
- [ ] `make check` passes.

## Verify (must exit 0, paste the tail into PROGRESS.md)
```bash
uv run pytest tests/evals -q && make eval SUITE=smoke
```

## Done when
All ACs are met, verify exits 0, `passes` for T026 is set to true, the task branch is merged into `milestone/M2`, and a PROGRESS.md entry is written. If blocked, write a BLOCKED entry with evidence and move on.
