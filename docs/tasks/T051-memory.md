# T051: Three-layer memory and retrieval

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol in `AGENTS.md`.

| | |
|---|---|
| Milestone | M4: Firms and memory (branch `milestone/M4`) |
| Depends on | T050 |
| Read first | SPEC §13 |
| Allowed to modify | `src/cre_brain/memory/**`, `tests/memory/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Sealed paths (see AGENTS.md), other tasks' entries, existing tests' assertions |

## Goal
Global, firm and user memory with retrieval into the lead prompt.

## Acceptance criteria
- [ ] AC1: Stores and access control per SPEC §13; test that firm A never retrieves firm B's items
- [ ] AC2: Retrieval of relevant playbook bullets and corrections within a token cap
- [ ] `make check` passes.

## Verify (must exit 0, paste the tail into PROGRESS.md)
```bash
uv run pytest tests/memory -q
```

## Done when
All ACs are met, verify exits 0, `passes` for T051 is set to true, the task branch is merged into `milestone/M4`, and a PROGRESS.md entry is written. If blocked, write a BLOCKED entry with evidence and move on.
