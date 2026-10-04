# T001: Repository scaffold

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol and branch model in `AGENTS.md` (work on `dev`).

| | |
|---|---|
| Milestone | M0: Guards and scaffold |
| Depends on | none |
| Read first | SPEC §1 |
| Allowed to modify | `pyproject.toml`, `uv.lock`, `Makefile`, `init.sh`, `.env.example`, `docker-compose.yml`, `src/cre_brain/**`, `tests/**`, `.pre-commit-config.yaml`, `brain/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Anything else in `scripts/protected_paths.txt`, `tests/conftest.py`; other tasks' entries; existing tests' assertions |
| Protected paths touched | No |

## Goal
Create the Python 3.12 project skeleton from SPEC §1. The guard scripts and CI come in T002.

## Acceptance criteria
Each ACn needs at least one passing, non-skipped test named `test_t001_ac<n>_*`.
- [ ] AC1 (`test_t001_ac1_*`): `pyproject.toml` (uv) defines `cre_brain` and the `cre` Typer CLI, with exact version pins; banned dependencies are absent
- [ ] AC2 (`test_t001_ac2_*`): ruff, mypy (strict on src/) and pytest + hypothesis are configured; `make check` runs lint, types and unit tests only (never verify_features)
- [ ] AC3 (`test_t001_ac3_*`): `init.sh` is idempotent; `docker-compose.yml` provides Postgres `db` for integration tests
- [ ] AC4 (`test_t001_ac4_*`): Package directories from SPEC §1 exist with `__init__.py`; `brain/` has placeholder skills/prompts/playbook
- [ ] AC5 (`test_t001_ac5_*`): `uv run cre --help` works; `.env.example` lists every env var name from AGENTS.md without values
- [ ] `make check` passes.

## Verify (must exit 0; paste the tail into PROGRESS.md)
```bash
./init.sh && make check && uv run cre --help && uv run pytest tests/test_t001_scaffold.py -q
```

## Done when
All ACs are met, verify exits 0, `passes` for T001 is true, the task branch is merged into `dev` and pushed, and a PROGRESS.md entry is written. If you are blocked, write a BLOCKED entry with evidence and move on.
