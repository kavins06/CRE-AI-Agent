# T050: Firm onboarding

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol in `AGENTS.md`.

| | |
|---|---|
| Milestone | M4: Firms and memory (branch `milestone/M4`) |
| Depends on | T038 |
| Read first | SPEC §14 |
| Allowed to modify | `src/cre_brain/onboarding/**`, `tests/onboarding/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Sealed paths (see AGENTS.md), other tasks' entries, existing tests' assertions |

## Goal
Adapt to each firm's template, criteria and memo style.

## Acceptance criteria
- [ ] AC1: The template mapper proposes a cell map for an uploaded firm workbook; parity on a synthetic deal must pass before it is saved
- [ ] AC2: Buy-box text/form → JDM tables, with rule tests generated from firm-confirmed examples
- [ ] AC3: Memo-style extraction → `firms/<id>/playbook/memo_style.md`
- [ ] AC4: `POST /firms/{id}/onboard`; test with 2 differently structured sample templates
- [ ] `make check` passes.

## Verify (must exit 0, paste the tail into PROGRESS.md)
```bash
uv run pytest tests/onboarding -q
```

## Done when
All ACs are met, verify exits 0, `passes` for T050 is set to true, the task branch is merged into `milestone/M4`, and a PROGRESS.md entry is written. If blocked, write a BLOCKED entry with evidence and move on.
