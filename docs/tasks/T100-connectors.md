# T100: Connector interfaces and stubs

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol and branch model in `AGENTS.md` (work on `dev`).

| | |
|---|---|
| Milestone | M8: Connectors, Jev, SDK runners, baseline |
| Depends on | T032 |
| Read first | SPEC §2; METHOD §3.6 |
| Allowed to modify | `src/cre_brain/connectors/**`, `tests/connectors/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Anything else in `scripts/protected_paths.txt`; other tasks' entries; existing tests' assertions |
| Protected paths touched | No |

## Goal
Ready-to-plug interfaces.

## Acceptance criteria
Each ACn needs at least one passing, non-skipped test named `test_t100_ac<n>_*`.
- [ ] AC1 (`test_t100_ac1_*`): Email, DataRoom, MarketData (public impl + CoStar/YardiMatrix/Trepp stubs), DocumentStore, Notifier with contract suites
- [ ] AC2 (`test_t100_ac2_*`): Stubs write to outbox; respect toggles
- [ ] `make check` passes.

## Verify (must exit 0; paste the tail into PROGRESS.md)
```bash
uv run pytest tests/connectors -q && uv run python scripts/check_task.py T100
```

## Done when
All ACs are met, verify exits 0, `passes` for T100 is true, the task branch is merged into `dev` and pushed, and a PROGRESS.md entry is written. If you are blocked, write a BLOCKED entry with evidence and move on.
