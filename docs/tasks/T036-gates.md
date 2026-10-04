# T036: Gate suite

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol in `AGENTS.md`.

| | |
|---|---|
| Milestone | M3: Agent (branch `milestone/M3`) |
| Depends on | T015, T016, T011 |
| Read first | SPEC §11; METHOD §4 |
| Allowed to modify | `src/cre_brain/gates/**`, `tests/protected/**`, `tests/gates/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Sealed paths (see AGENTS.md), other tasks' entries, existing tests' assertions |

## Goal
Every gate in SPEC §11 with contract tests.

## Acceptance criteria
- [ ] AC1: Gates: coverage, checksums, parity, excel_errors, assumption_ranges, irr_sanity, fragility, provenance_entailment, numbers_match_model, policy_bands, verifier
- [ ] AC2: The catalog maps each DeliverableKind to its gates per SPEC §11
- [ ] AC3: Each gate has pass/fail contract tests in `tests/protected/` using planted failures
- [ ] `make check` passes.

## Verify (must exit 0, paste the tail into PROGRESS.md)
```bash
uv run pytest tests/gates tests/protected -q
```

## Done when
All ACs are met, verify exits 0, `passes` for T036 is set to true, the task branch is merged into `milestone/M3`, and a PROGRESS.md entry is written. If blocked, write a BLOCKED entry with evidence and move on.
