# T071: GEPA proposer with Codex LM

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol and branch model in `AGENTS.md` (work on `dev`).

| | |
|---|---|
| Milestone | M5: Learning loop (overnight self-improvement) |
| Depends on | T070 |
| Read first | LEARNING §4; LIBRARY_NOTES GEPA |
| Allowed to modify | `learning/gepa_proposer.py`, `tests/learning/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Anything else in `scripts/protected_paths.txt`; other tasks' entries; existing tests' assertions |
| Protected paths touched | No |

## Goal
One edit per call, no LiteLLM.

## Acceptance criteria
Each ACn needs at least one passing, non-skipped test named `test_t071_ac<n>_*`.
- [ ] AC1 (`test_t071_ac1_*`): Custom LM callable wrapping `codex exec -p reflector`; dspy/litellm absent from lockfile (test)
- [ ] AC2 (`test_t071_ac2_*`): Proposer returns exactly one edited artifact; sees only failure categories (test asserts no rubric/holdout text in inputs)
- [ ] `make check` passes.

## Verify (must exit 0; paste the tail into PROGRESS.md)
```bash
uv run pytest tests/learning -q -k gepa && uv run python scripts/check_task.py T071
```

## Done when
All ACs are met, verify exits 0, `passes` for T071 is true, the task branch is merged into `dev` and pushed, and a PROGRESS.md entry is written. If you are blocked, write a BLOCKED entry with evidence and move on.
