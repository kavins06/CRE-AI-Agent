# T061: GEPA adapters

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol in `AGENTS.md`.

| | |
|---|---|
| Milestone | M5: Learning loop (branch `milestone/M5`) |
| Depends on | T060 |
| Read first | LEARNING §4; LIBRARY_NOTES GEPA |
| Allowed to modify | `learning/**`, `tests/learning/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Sealed paths (see AGENTS.md), other tasks' entries, existing tests' assertions |

## Goal
Edit proposals from failure categories only.

## Acceptance criteria
- [ ] AC1: One adapter per deliverable kind over brain/ artifacts
- [ ] AC2: The evaluator returns only failure categories (test asserts that no rubric text or holdout content leaks)
- [ ] `make check` passes.

## Verify (must exit 0, paste the tail into PROGRESS.md)
```bash
uv run pytest tests/learning -q -k gepa
```

## Done when
All ACs are met, verify exits 0, `passes` for T061 is set to true, the task branch is merged into `milestone/M5`, and a PROGRESS.md entry is written. If blocked, write a BLOCKED entry with evidence and move on.
