# T037: Deterministic gates

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol and branch model in `AGENTS.md` (work on `dev`).

| | |
|---|---|
| Milestone | M2: First working analyst (thin slice: SCREEN + UW_MODEL via cre run) |
| Depends on | T020, T021, T012, T018 |
| Read first | SPEC §11 |
| Allowed to modify | `src/cre_brain/gates/**`, `tests/protected/**`, `tests/gates/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Anything else in `scripts/protected_paths.txt`; other tasks' entries; existing tests' assertions |
| Protected paths touched | Yes. The milestone PR needs the owner's `protected-change` label |

## Goal
All blocking gates for v1.

## Acceptance criteria
Each ACn needs at least one passing, non-skipped test named `test_t037_ac<n>_*`.
- [ ] AC1 (`test_t037_ac1_*`): coverage, checksums (typed tolerances), parity, excel_errors, assumption_ranges, irr_sanity, fragility (margin-based), buy_box, number_provenance, numbers_match_model, required_sections, policy_bands
- [ ] AC2 (`test_t037_ac2_*`): number_provenance extracts every number from prose/tables and requires a CalcResult/Fact match
- [ ] AC3 (`test_t037_ac3_*`): Catalog maps each DeliverableKind to gates per SPEC §11; LLM gates (entailment, verifier) registered as advisory
- [ ] AC4 (`test_t037_ac4_*`): Pass/fail contract tests per gate in tests/protected/ with planted failures
- [ ] `make check` passes.

## Verify (must exit 0; paste the tail into PROGRESS.md)
```bash
uv run pytest tests/gates tests/protected -q && uv run python scripts/check_task.py T037
```

## Done when
All ACs are met, verify exits 0, `passes` for T037 is true, the task branch is merged into `dev` and pushed, and a PROGRESS.md entry is written. If you are blocked, write a BLOCKED entry with evidence and move on.
