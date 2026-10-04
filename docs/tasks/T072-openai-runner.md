# T072: OpenAI Agents SDK runner

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol in `AGENTS.md`.

| | |
|---|---|
| Milestone | M6: Connectors and portability (branch `milestone/M6`) |
| Depends on | T041 |
| Read first | METHOD §3.1 |
| Allowed to modify | `src/cre_brain/runner/openai_runner.py`, `tests/runner/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Sealed paths (see AGENTS.md), other tasks' entries, existing tests' assertions |

## Goal
A second runner sharing tools, skills and gates, compared on evals.

## Acceptance criteria
- [ ] AC1: `OpenAIRunner` implements `Runner` with the same CRE tools, policy and gates
- [ ] AC2: `cre evals compare-runners` produces a side-by-side report (skips without keys)
- [ ] `make check` passes.

## Verify (must exit 0, paste the tail into PROGRESS.md)
```bash
uv run pytest tests/runner -q -k openai
```

## Done when
All ACs are met, verify exits 0, `passes` for T072 is set to true, the task branch is merged into `milestone/M6`, and a PROGRESS.md entry is written. If blocked, write a BLOCKED entry with evidence and move on.
