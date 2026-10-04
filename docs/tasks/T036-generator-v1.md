# T036: Synthetic generator v1 (rent roll, T-12, OM)

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol and branch model in `AGENTS.md` (work on `dev`).

| | |
|---|---|
| Milestone | M2: First working analyst (thin slice: SCREEN + UW_MODEL via cre run) |
| Depends on | T018, T034 |
| Read first | EVALS §1–2 |
| Allowed to modify | `evals/generator/**`, `tests/evals/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Anything else in `scripts/protected_paths.txt`; other tasks' entries; existing tests' assertions |
| Protected paths touched | Yes. The milestone PR needs the owner's `protected-change` label |

## Goal
Calibratable latent-deal generator writing packages and truth to separate dirs.

## Acceptance criteria
Each ACn needs at least one passing, non-skipped test named `test_t036_ac<n>_*`.
- [ ] AC1 (`test_t036_ac1_*`): Latent deal sampler with documented default priors (calibration to public data comes in T050)
- [ ] AC2 (`test_t036_ac2_*`): Renderers: rent roll (3 layouts, XLSX/CSV), T-12 XLSX, OM PDF
- [ ] AC3 (`test_t036_ac3_*`): `cre evals gen --n 20 --seed S --out-packages P --out-truth T` writes packages and truth to separate directories; truth computed with cre_brain.finance only
- [ ] `make check` passes.

## Verify (must exit 0; paste the tail into PROGRESS.md)
```bash
uv run pytest tests/evals -q -k generator && uv run python scripts/check_task.py T036
```

## Done when
All ACs are met, verify exits 0, `passes` for T036 is true, the task branch is merged into `dev` and pushed, and a PROGRESS.md entry is written. If you are blocked, write a BLOCKED entry with evidence and move on.
