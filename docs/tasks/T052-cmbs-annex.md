# T052: Annex A-1/A-3 fixtures and matching

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol and branch model in `AGENTS.md` (work on `dev`).

| | |
|---|---|
| Milestone | M3: Evals on real anchors |
| Depends on | T051 |
| Read first | EVALS §2 C |
| Allowed to modify | `evals/cmbs/**`, `tests/evals/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Anything else in `scripts/protected_paths.txt`; other tasks' entries; existing tests' assertions |
| Protected paths touched | Yes. The milestone PR needs the owner's `protected-change` label |

## Goal
Real document fixtures matched to EX-102 truth.

## Acceptance criteria
Each ACn needs at least one passing, non-skipped test named `test_t052_ac<n>_*`.
- [ ] AC1 (`test_t052_ac1_*`): Collect A-1 tables + A-3 narratives for MF loans; match to EX-102 by deal + asset number/name
- [ ] AC2 (`test_t052_ac2_*`): Package (document) and truth (EX-102 securitization) written to separate dirs; names/addresses/ids anonymized, numbers kept
- [ ] AC3 (`test_t052_ac3_*`): Matching precision checked on fixtures
- [ ] `make check` passes.

## Verify (must exit 0; paste the tail into PROGRESS.md)
```bash
uv run pytest tests/evals -q -k annex && uv run python scripts/check_task.py T052
```

## Done when
All ACs are met, verify exits 0, `passes` for T052 is true, the task branch is merged into `dev` and pushed, and a PROGRESS.md entry is written. If you are blocked, write a BLOCKED entry with evidence and move on.
