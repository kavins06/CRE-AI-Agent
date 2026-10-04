# T014: Excel reference template and writer

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol in `AGENTS.md`.

| | |
|---|---|
| Milestone | M1: Domain core (branch `milestone/M1`) |
| Depends on | T013 |
| Read first | SPEC §7 |
| Allowed to modify | `src/cre_brain/excel/**`, `tests/excel/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Sealed paths (see AGENTS.md), other tasks' entries, existing tests' assertions |

## Goal
A code-generated multifamily UW template with named ranges and a JSON cell map.

## Acceptance criteria
- [ ] AC1: `excel/build_template.py` generates `templates/mf_standard.xlsx` using only whitelisted functions (from `gates.yaml`) and no circular references
- [ ] AC2: `templates/mf_standard.map.json` maps every calc_id and fact key to sheet!cell
- [ ] AC3: `writer.py` fills the inputs for a deal from state
- [ ] AC4: Test: generated workbook formulas reference only whitelisted functions
- [ ] `make check` passes.

## Verify (must exit 0, paste the tail into PROGRESS.md)
```bash
uv run pytest tests/excel -q -k template
```

## Done when
All ACs are met, verify exits 0, `passes` for T014 is set to true, the task branch is merged into `milestone/M1`, and a PROGRESS.md entry is written. If blocked, write a BLOCKED entry with evidence and move on.
