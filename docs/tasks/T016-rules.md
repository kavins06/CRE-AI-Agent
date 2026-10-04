# T016: Rules engine and default tables

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol in `AGENTS.md`.

| | |
|---|---|
| Milestone | M1: Domain core (branch `milestone/M1`) |
| Depends on | T010 |
| Read first | SPEC §8; LIBRARY_NOTES zen-engine |
| Allowed to modify | `src/cre_brain/rules/**`, `tests/rules/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Sealed paths (see AGENTS.md), other tasks' entries, existing tests' assertions |

## Goal
zen-engine wrapper and the default JDM decision tables.

## Acceptance criteria
- [ ] AC1: `rules.evaluate(table, input)` returns a typed result + trace
- [ ] AC2: Tables exist: `buy_box.default`, `assumption_ranges.mf`, `loi_policy.default`, `missing_data_policy`, `escalation_policy`
- [ ] AC3: Each table has example-based tests (≥5 cases each)
- [ ] `make check` passes.

## Verify (must exit 0, paste the tail into PROGRESS.md)
```bash
uv run pytest tests/rules -q
```

## Done when
All ACs are met, verify exits 0, `passes` for T016 is set to true, the task branch is merged into `milestone/M1`, and a PROGRESS.md entry is written. If blocked, write a BLOCKED entry with evidence and move on.
