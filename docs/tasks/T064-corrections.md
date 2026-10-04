# T064: DAgger correction capture

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol in `AGENTS.md`.

| | |
|---|---|
| Milestone | M5: Learning loop (branch `milestone/M5`) |
| Depends on | T051, T026 |
| Read first | LEARNING §6 |
| Allowed to modify | `src/cre_brain/control/corrections.py`, `tests/control/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Sealed paths (see AGENTS.md), other tasks' entries, existing tests' assertions |

## Goal
Every user correction becomes training signal.

## Acceptance criteria
- [ ] AC1: `POST /corrections` and `cre correct` store a DecisionRecord
- [ ] AC2: Each record → private eval case + memory item + candidate lesson (fact/convention only)
- [ ] `make check` passes.

## Verify (must exit 0, paste the tail into PROGRESS.md)
```bash
uv run pytest tests/control -q -k corrections
```

## Done when
All ACs are met, verify exits 0, `passes` for T064 is set to true, the task branch is merged into `milestone/M5`, and a PROGRESS.md entry is written. If blocked, write a BLOCKED entry with evidence and move on.
