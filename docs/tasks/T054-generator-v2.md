# T054: Generator v2: leases and third-party reports

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol and branch model in `AGENTS.md` (work on `dev`).

| | |
|---|---|
| Milestone | M3: Evals on real anchors |
| Depends on | T036 |
| Read first | EVALS §2 A |
| Allowed to modify | `evals/generator/**`, `tests/evals/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Anything else in `scripts/protected_paths.txt`; other tasks' entries; existing tests' assertions |
| Protected paths touched | Yes. The milestone PR needs the owner's `protected-change` label |

## Goal
Render all document types defects need.

## Acceptance criteria
Each ACn needs at least one passing, non-skipped test named `test_t054_ac<n>_*`.
- [ ] AC1 (`test_t054_ac1_*`): Lease PDFs with amendments; estoppels; Phase I, PCA, title commitment, zoning letter summaries; debt term sheets; comp sets
- [ ] AC2 (`test_t054_ac2_*`): Truth for each written separately
- [ ] `make check` passes.

## Verify (must exit 0; paste the tail into PROGRESS.md)
```bash
uv run pytest tests/evals -q -k generator_v2 && uv run python scripts/check_task.py T054
```

## Done when
All ACs are met, verify exits 0, `passes` for T054 is true, the task branch is merged into `dev` and pushed, and a PROGRESS.md entry is written. If you are blocked, write a BLOCKED entry with evidence and move on.
