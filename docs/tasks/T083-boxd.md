# T083: Box agent cre-boxd

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol and branch model in `AGENTS.md` (work on `dev`).

| | |
|---|---|
| Milestone | M6: Platform (API, box agent, recovery, stress) |
| Depends on | T031, T033, T080 |
| Read first | SPEC §10.8 |
| Allowed to modify | `src/cre_brain/sandbox/boxd/**`, `tests/sandbox/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Anything else in `scripts/protected_paths.txt`; other tasks' entries; existing tests' assertions |
| Protected paths touched | No |

## Goal
Outbound link, idempotent segments, acks.

## Acceptance criteria
Each ACn needs at least one passing, non-skipped test named `test_t083_ac<n>_*`.
- [ ] AC1 (`test_t083_ac1_*`): Outbound authenticated WebSocket; start_or_attach idempotent on box side; interrupt/pause/resume/deliver_message/sync_playbook
- [ ] AC2 (`test_t083_ac2_*`): Events with origin; acks; resend after reconnect; dedupe; heartbeats
- [ ] `make check` passes.

## Verify (must exit 0; paste the tail into PROGRESS.md)
```bash
uv run pytest tests/sandbox -q -k boxd && uv run python scripts/check_task.py T083
```

## Done when
All ACs are met, verify exits 0, `passes` for T083 is true, the task branch is merged into `dev` and pushed, and a PROGRESS.md entry is written. If you are blocked, write a BLOCKED entry with evidence and move on.
