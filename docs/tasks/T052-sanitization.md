# T052: Sanitization gate

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol in `AGENTS.md`.

| | |
|---|---|
| Milestone | M4: Firms and memory (branch `milestone/M4`) |
| Depends on | T051 |
| Read first | SPEC §13 |
| Allowed to modify | `src/cre_brain/memory/sanitize.py`, `tests/protected/**`, `tests/memory/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Sealed paths (see AGENTS.md), other tasks' entries, existing tests' assertions |

## Goal
Nothing firm-specific reaches the global brain.

## Acceptance criteria
- [ ] AC1: Scrubber: NER + deal-entity dictionary + number bucketing + quote removal
- [ ] AC2: Fails closed on any residual entity match
- [ ] AC3: Contract tests with ≥50 planted leaks; 100% caught
- [ ] `make check` passes.

## Verify (must exit 0, paste the tail into PROGRESS.md)
```bash
uv run pytest tests/protected -q -k sanitize
```

## Done when
All ACs are met, verify exits 0, `passes` for T052 is set to true, the task branch is merged into `milestone/M4`, and a PROGRESS.md entry is written. If blocked, write a BLOCKED entry with evidence and move on.
