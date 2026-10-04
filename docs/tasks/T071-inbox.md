# T071: Inbox ingestion

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol in `AGENTS.md`.

| | |
|---|---|
| Milestone | M6: Connectors and portability (branch `milestone/M6`) |
| Depends on | T040 |
| Read first | SPEC §3 |
| Allowed to modify | `src/cre_brain/control/**`, `tests/control/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Sealed paths (see AGENTS.md), other tasks' entries, existing tests' assertions |

## Goal
Files dropped in `inbox/` become tasks.

## Acceptance criteria
- [ ] AC1: A watcher creates a task per new deal package; the user can attach a request note
- [ ] AC2: Idempotent on re-drop
- [ ] `make check` passes.

## Verify (must exit 0, paste the tail into PROGRESS.md)
```bash
uv run pytest tests/control -q -k inbox
```

## Done when
All ACs are met, verify exits 0, `passes` for T071 is set to true, the task branch is merged into `milestone/M6`, and a PROGRESS.md entry is written. If blocked, write a BLOCKED entry with evidence and move on.
