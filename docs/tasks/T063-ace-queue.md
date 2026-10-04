# T063: ACE playbook queue and promotion

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol in `AGENTS.md`.

| | |
|---|---|
| Milestone | M5: Learning loop (branch `milestone/M5`) |
| Depends on | T052, T062 |
| Read first | LEARNING §5 |
| Allowed to modify | `src/cre_brain/memory/ace_queue.py`, `learning/**`, `tests/learning/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Sealed paths (see AGENTS.md), other tasks' entries, existing tests' assertions |

## Goal
Lessons are proposed live and promoted only through the ratchet.

## Acceptance criteria
- [ ] AC1: Candidates only from deterministic signals; bullet metadata per LEARNING §5; cap and contradiction check
- [ ] AC2: Promotion = sanitization + keep rule on fixtures; live runs cannot write `brain/playbook/global.md` (test)
- [ ] `make check` passes.

## Verify (must exit 0, paste the tail into PROGRESS.md)
```bash
uv run pytest tests/learning -q -k ace
```

## Done when
All ACs are met, verify exits 0, `passes` for T063 is set to true, the task branch is merged into `milestone/M5`, and a PROGRESS.md entry is written. If blocked, write a BLOCKED entry with evidence and move on.
