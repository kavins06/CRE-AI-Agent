# T056: Adversarial set

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol and branch model in `AGENTS.md` (work on `dev`).

| | |
|---|---|
| Milestone | M3: Evals on real anchors |
| Depends on | T054 |
| Read first | EVALS §2 F |
| Allowed to modify | `evals/adversarial/**`, `tests/evals/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Anything else in `scripts/protected_paths.txt`; other tasks' entries; existing tests' assertions |
| Protected paths touched | Yes. The milestone PR needs the owner's `protected-change` label |

## Goal
Injection, contradiction, missing docs, malicious web pages.

## Acceptance criteria
Each ACn needs at least one passing, non-skipped test named `test_t056_ac<n>_*`.
- [ ] AC1 (`test_t056_ac1_*`): ≥60 cases with expected safe behaviour labels
- [ ] AC2 (`test_t056_ac2_*`): Includes injections targeting extraction (exfiltrate other files) — expected: blocked by container isolation
- [ ] `make check` passes.

## Verify (must exit 0; paste the tail into PROGRESS.md)
```bash
uv run pytest tests/evals -q -k adversarial && uv run python scripts/check_task.py T056
```

## Done when
All ACs are met, verify exits 0, `passes` for T056 is true, the task branch is merged into `dev` and pushed, and a PROGRESS.md entry is written. If you are blocked, write a BLOCKED entry with evidence and move on.
