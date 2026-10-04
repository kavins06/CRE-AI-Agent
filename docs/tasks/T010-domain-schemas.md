# T010: Domain schemas

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol in `AGENTS.md`.

| | |
|---|---|
| Milestone | M1: Domain core (branch `milestone/M1`) |
| Depends on | T001 |
| Read first | SPEC §4 |
| Allowed to modify | `src/cre_brain/domain/**`, `tests/domain/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Sealed paths (see AGENTS.md), other tasks' entries, existing tests' assertions |

## Goal
Pydantic v2 models for Fact, Provenance, ClaimType, Assumption, CalcResult, Question, Deliverable and Task, exactly as in SPEC §4.

## Acceptance criteria
- [ ] AC1: All models from SPEC §4 exist with field types; money uses `Decimal`
- [ ] AC2: `DeliverableKind` enum matches SPEC §4
- [ ] AC3: JSON round-trip tests for every model; hypothesis strategies exported for reuse in later tests
- [ ] `make check` passes.

## Verify (must exit 0, paste the tail into PROGRESS.md)
```bash
uv run pytest tests/domain -q
```

## Done when
All ACs are met, verify exits 0, `passes` for T010 is set to true, the task branch is merged into `milestone/M1`, and a PROGRESS.md entry is written. If blocked, write a BLOCKED entry with evidence and move on.
