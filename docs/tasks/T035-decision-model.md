# T035: DecisionModel: Jev + fallback

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol in `AGENTS.md`.

| | |
|---|---|
| Milestone | M3: Agent (branch `milestone/M3`) |
| Depends on | T003 |
| Read first | SPEC §2; LIBRARY_NOTES typesafe-sdk |
| Allowed to modify | `src/cre_brain/decisions/**`, `tests/decisions/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Sealed paths (see AGENTS.md), other tasks' entries, existing tests' assertions |

## Goal
Fast typed decisions behind one interface.

## Acceptance criteria
- [ ] AC1: `JevDecisionModel` (typesafe-sdk) and `LLMDecisionModel` (fast_decision fallback model)
- [ ] AC2: Uses Jev only if a key exists AND `config` marks it calibrated; otherwise the fallback
- [ ] AC3: Document-type classification and request-routing helpers; a calibration script producing reliability stats on labelled cases
- [ ] `make check` passes.

## Verify (must exit 0, paste the tail into PROGRESS.md)
```bash
uv run pytest tests/decisions -q
```

## Done when
All ACs are met, verify exits 0, `passes` for T035 is set to true, the task branch is merged into `milestone/M3`, and a PROGRESS.md entry is written. If blocked, write a BLOCKED entry with evidence and move on.
