# T082: Event paging, SSE, redaction

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol and branch model in `AGENTS.md` (work on `dev`).

| | |
|---|---|
| Milestone | M6: Platform (API, box agent, recovery, stress) |
| Depends on | T080 |
| Read first | SPEC §4, §12, §15 |
| Allowed to modify | `src/cre_brain/control/**`, `src/cre_brain/runner/redact.py`, `tests/protected/**`, `tests/control/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Anything else in `scripts/protected_paths.txt`; other tasks' entries; existing tests' assertions |
| Protected paths touched | Yes. The milestone PR needs the owner's `protected-change` label |

## Goal
Safe, resumable event streams.

## Acceptance criteria
Each ACn needs at least one passing, non-skipped test named `test_t082_ac<n>_*`.
- [ ] AC1 (`test_t082_ac1_*`): GET events with after_seq/limit; SSE with Last-Event-ID
- [ ] AC2 (`test_t082_ac2_*`): Redaction before storage/stream; planted-secret tests 100% (tests/protected)
- [ ] `make check` passes.

## Verify (must exit 0; paste the tail into PROGRESS.md)
```bash
uv run pytest tests/control -q -k events && uv run pytest tests/protected -q -k redact && uv run python scripts/check_task.py T082
```

## Done when
All ACs are met, verify exits 0, `passes` for T082 is true, the task branch is merged into `dev` and pushed, and a PROGRESS.md entry is written. If you are blocked, write a BLOCKED entry with evidence and move on.
