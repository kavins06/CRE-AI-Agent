# T064: LOI and broker questions

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol and branch model in `AGENTS.md` (work on `dev`).

| | |
|---|---|
| Milestone | M4: Full analyst deliverables |
| Depends on | T039, T037 |
| Read first | SPEC §11 |
| Allowed to modify | `src/cre_brain/deliverables/loi/**`, `src/cre_brain/deliverables/broker/**`, `brain/skills/**`, `tests/deliverables/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Anything else in `scripts/protected_paths.txt`; other tasks' entries; existing tests' assertions |
| Protected paths touched | No |

## Goal
Offer and information requests.

## Acceptance criteria
Each ACn needs at least one passing, non-skipped test named `test_t064_ac<n>_*`.
- [ ] AC1 (`test_t064_ac1_*`): LOI from max-supportable price + loi_policy bands; drafts to outbox (never sent unless toggled)
- [ ] AC2 (`test_t064_ac2_*`): Broker question/request list derived from coverage gaps and open questions
- [ ] `make check` passes.

## Verify (must exit 0; paste the tail into PROGRESS.md)
```bash
uv run pytest tests/deliverables -q -k 'loi or broker' && uv run python scripts/check_task.py T064
```

## Done when
All ACs are met, verify exits 0, `passes` for T064 is true, the task branch is merged into `dev` and pushed, and a PROGRESS.md entry is written. If you are blocked, write a BLOCKED entry with evidence and move on.
