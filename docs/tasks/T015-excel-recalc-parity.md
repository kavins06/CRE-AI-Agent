# T015: Recalculation and Python–Excel parity

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol in `AGENTS.md`.

| | |
|---|---|
| Milestone | M1: Domain core (branch `milestone/M1`) |
| Depends on | T014 |
| Read first | SPEC §7; LIBRARY_NOTES LibreOffice |
| Allowed to modify | `src/cre_brain/excel/**`, `tests/excel/**`, `docker/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Sealed paths (see AGENTS.md), other tasks' entries, existing tests' assertions |

## Goal
Recalculate with LibreOffice headless and diff every output against Python.

## Acceptance criteria
- [ ] AC1: The `ExcelEngine` protocol, with `LibreOfficeEngine` using the UNO macro method from LIBRARY_NOTES (one profile per call)
- [ ] AC2: `parity.py` compares the recalculated values with the Python CalcResults within `gates.yaml` tolerances and reports per-cell diffs
- [ ] AC3: Error scan detects `#REF!`, `#DIV/0!`, `#VALUE!` and `#NAME?`
- [ ] AC4: `GraphExcelEngine` adapter stub plus contract tests, skipped without `MS_GRAPH_*`
- [ ] AC5: Test: a synthetic deal produces parity PASS; a planted formula error produces FAIL with the cell address
- [ ] `make check` passes.

## Verify (must exit 0, paste the tail into PROGRESS.md)
```bash
uv run pytest tests/excel -q
```

## Done when
All ACs are met, verify exits 0, `passes` for T015 is set to true, the task branch is merged into `milestone/M1`, and a PROGRESS.md entry is written. If blocked, write a BLOCKED entry with evidence and move on.
