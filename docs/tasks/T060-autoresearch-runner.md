# T060: Autoresearch runner

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol in `AGENTS.md`.

| | |
|---|---|
| Milestone | M5: Learning loop (branch `milestone/M5`) |
| Depends on | T026, T041 |
| Read first | LEARNING §2, §8; program.md |
| Allowed to modify | `learning/**`, `tests/learning/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Sealed paths (see AGENTS.md), other tasks' entries, existing tests' assertions |

## Goal
Karpathy-style experiment loop on frozen per-deliverable fixtures.

## Acceptance criteria
- [ ] AC1: Fixture builder checkpoints deal state just before each deliverable kind
- [ ] AC2: The loop follows program.md: branch, one artifact edit, k=3 eval, keep/revert, `results.tsv`, PR at the end
- [ ] AC3: Analyst sessions via CodexRunner; scoring as a separate blind process; skips cleanly without a runner; stops at session/wall-clock caps
- [ ] `make check` passes.

## Verify (must exit 0, paste the tail into PROGRESS.md)
```bash
uv run pytest tests/learning -q -k runner
```

## Done when
All ACs are met, verify exits 0, `passes` for T060 is set to true, the task branch is merged into `milestone/M5`, and a PROGRESS.md entry is written. If blocked, write a BLOCKED entry with evidence and move on.
