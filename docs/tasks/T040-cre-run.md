# T040: `cre run` orchestration (jobs, segments, stuck, escalation)

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol and branch model in `AGENTS.md` (work on `dev`).

| | |
|---|---|
| Milestone | M2: First working analyst (thin slice: SCREEN + UW_MODEL via cre run) |
| Depends on | T039, T011 |
| Read first | SPEC §10.1, §10.3, §12 |
| Allowed to modify | `src/cre_brain/runner/**`, `src/cre_brain/control/jobs.py`, `tests/runner/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Anything else in `scripts/protected_paths.txt`; other tasks' entries; existing tests' assertions |
| Protected paths touched | No |

## Goal
Run a request on a deal end to end locally.

## Acceptance criteria
Each ACn needs at least one passing, non-skipped test named `test_t040_ac<n>_*`.
- [ ] AC1 (`test_t040_ac1_*`): `cre run --deal <path> --request "..."`: pre-parse → extraction → lead analyst segments (CodexRunner) → deliverables
- [ ] AC2 (`test_t040_ac2_*`): Jobs table with unique (task_id, segment_no); a killed run resumes without a duplicate session
- [ ] AC3 (`test_t040_ac3_*`): Stuck detector (repeated call/result, repeated errors, no progress) → nudge → stop → ESCALATION deliverable
- [ ] AC4 (`test_t040_ac4_*`): Budget meter from usage events; escalation deliverable on cap
- [ ] `make check` passes.

## Verify (must exit 0; paste the tail into PROGRESS.md)
```bash
uv run pytest tests/runner -q -k 'run or stuck or jobs' && uv run python scripts/check_task.py T040
```

## Done when
All ACs are met, verify exits 0, `passes` for T040 is true, the task branch is merged into `dev` and pushed, and a PROGRESS.md entry is written. If you are blocked, write a BLOCKED entry with evidence and move on.
