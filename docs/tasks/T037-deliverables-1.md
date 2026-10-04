# T037: Deliverables I: screen, broker questions, lease abstracts

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol in `AGENTS.md`.

| | |
|---|---|
| Milestone | M3: Agent (branch `milestone/M3`) |
| Depends on | T034, T035, T036 |
| Read first | SPEC §10.6; METHOD §3.4 |
| Allowed to modify | `src/cre_brain/deliverables/**`, `brain/skills/**`, `brain/prompts/**`, `tests/deliverables/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Sealed paths (see AGENTS.md), other tasks' entries, existing tests' assertions |

## Goal
The screen-first fast path and three quick deliverables.

## Acceptance criteria
- [ ] AC1: SCREEN: classify → headline extraction → buy-box → memo (Markdown + JSON), p50 ≤5 min target recorded
- [ ] AC2: BROKER_QUESTIONS and LEASE_ABSTRACT deliverables with provenance
- [ ] AC3: A Skill per deliverable in `brain/skills/` (SKILL.md + scripts)
- [ ] AC4: Gates pass on synthetic fixtures
- [ ] `make check` passes.

## Verify (must exit 0, paste the tail into PROGRESS.md)
```bash
uv run pytest tests/deliverables -q -k 'screen or broker or lease'
```

## Done when
All ACs are met, verify exits 0, `passes` for T037 is set to true, the task branch is merged into `milestone/M3`, and a PROGRESS.md entry is written. If blocked, write a BLOCKED entry with evidence and move on.
