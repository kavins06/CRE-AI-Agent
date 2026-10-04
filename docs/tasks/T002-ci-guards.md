# T002: CI workflow and anti-gaming guards

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol in `AGENTS.md`.

| | |
|---|---|
| Milestone | M0: Scaffold and guards (branch `milestone/M0`) |
| Depends on | T001 |
| Read first | AGENTS.md Forbidden actions; EVALS §1 |
| Allowed to modify | `.github/workflows/**`, `scripts/**`, `PROTECTED_HASHES.txt`, `tests/test_guards.py`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Sealed paths (see AGENTS.md), other tasks' entries, existing tests' assertions |

## Goal
Add CI that runs the checks and makes test-gaming mechanically impossible.

## Acceptance criteria
- [ ] AC1: `.github/workflows/ci.yml` runs jobs `check`, `protected-hashes`, `test-count` and `verify-features` on every PR
- [ ] AC2: `scripts/check_protected.py` computes SHA-256 hashes of sealed paths (configured list in `scripts/protected_paths.txt`) and fails on any mismatch with `PROTECTED_HASHES.txt`; a `--update` flag exists for owner use
- [ ] AC3: `scripts/test_count.py` fails if the collected test count drops below the count on the base branch, or if new `skip`/`xfail` markers appear
- [ ] AC4: `scripts/verify_features.py` re-runs the `verify` command of every task with `passes: true` and fails if any exits non-zero
- [ ] AC5: `tests/test_guards.py` proves each script detects a planted violation
- [ ] `make check` passes.

## Verify (must exit 0, paste the tail into PROGRESS.md)
```bash
uv run pytest tests/test_guards.py -q && uv run python scripts/check_protected.py
```

## Done when
All ACs are met, verify exits 0, `passes` for T002 is set to true, the task branch is merged into `milestone/M0`, and a PROGRESS.md entry is written. If blocked, write a BLOCKED entry with evidence and move on.
