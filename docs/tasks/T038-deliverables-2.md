# T038: Deliverables II: UW model, IC memo, DD tracker, LOI, comparison

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol in `AGENTS.md`.

| | |
|---|---|
| Milestone | M3: Agent (branch `milestone/M3`) |
| Depends on | T037 |
| Read first | SPEC §7, §11; METHOD §3.4 |
| Allowed to modify | `src/cre_brain/deliverables/**`, `brain/skills/**`, `brain/prompts/**`, `tests/deliverables/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Sealed paths (see AGENTS.md), other tasks' entries, existing tests' assertions |

## Goal
The full analyst deliverables.

## Acceptance criteria
- [ ] AC1: UW_MODEL: Python model + Excel (firm template if mapped, else mf_standard) with parity
- [ ] AC2: IC_MEMO with every number traced; DD_TRACKER + issues log; LOI within policy bands; DEAL_COMPARISON
- [ ] AC3: A Skill per deliverable; all gates pass on synthetic fixtures
- [ ] `make check` passes.

## Verify (must exit 0, paste the tail into PROGRESS.md)
```bash
uv run pytest tests/deliverables -q
```

## Done when
All ACs are met, verify exits 0, `passes` for T038 is set to true, the task branch is merged into `milestone/M3`, and a PROGRESS.md entry is written. If blocked, write a BLOCKED entry with evidence and move on.
