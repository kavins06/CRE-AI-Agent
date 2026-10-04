# T002: CI checks, task checker, skip markers

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol and branch model in `AGENTS.md` (work on `dev`).

| | |
|---|---|
| Milestone | M0: Guards and scaffold |
| Depends on | T001 |
| Read first | AGENTS.md (Forbidden, Commands); EVALS §6 |
| Allowed to modify | `.github/workflows/ci.yml`, `scripts/check_task.py`, `scripts/test_count.py`, `scripts/verify_features.py`, `tests/conftest.py`, `tests/test_t002_*.py`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Anything else in `scripts/protected_paths.txt`; other tasks' entries; existing tests' assertions |
| Protected paths touched | Yes. The milestone PR needs the owner's `protected-change` label |

## Goal
Make test-gaming mechanically hard. Note: `guards.yml`, `check_protected.py` and `protected_paths.txt` are owner-authored. Do not edit them.

## Acceptance criteria
Each ACn needs at least one passing, non-skipped test named `test_t002_ac<n>_*`.
- [ ] AC1 (`test_t002_ac1_*`): `tests/conftest.py` defines the ONLY approved skip markers: `requires_codex`, `requires_network`, `requires_key(NAME)`, `requires_license(NAME)`; any other skip/xfail fails collection
- [ ] AC2 (`test_t002_ac2_*`): `scripts/check_task.py <ID>` parses the task file's ACs and requires, for each ACn, at least one PASSED non-skipped test named `test_<id>_ac<n>_*`; it also fails if all tests in the task's area are skipped
- [ ] AC3 (`test_t002_ac3_*`): `scripts/test_count.py` fails if the collected test count on HEAD is lower than on the base branch
- [ ] AC4 (`test_t002_ac4_*`): `scripts/verify_features.py` re-runs `verify` of passing tasks; it is run only in the `ci.yml` job on PRs to `main` and nightly, never by `make check`
- [ ] AC5 (`test_t002_ac5_*`): `.github/workflows/ci.yml` runs jobs `check` (make check) and `test-count` on PRs to dev/main, and `verify-features` on PRs to main; Docker images cached
- [ ] AC6 (`test_t002_ac6_*`): Tests prove each script catches a planted violation (missing AC test, unapproved skip, dropped test count)
- [ ] `make check` passes.

## Verify (must exit 0; paste the tail into PROGRESS.md)
```bash
make check && uv run pytest tests/test_t002_guards.py -q && uv run python scripts/check_task.py T002
```

## Done when
All ACs are met, verify exits 0, `passes` for T002 is true, the task branch is merged into `dev` and pushed, and a PROGRESS.md entry is written. If you are blocked, write a BLOCKED entry with evidence and move on.
