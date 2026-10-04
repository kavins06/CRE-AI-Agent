# T001: Repository scaffold

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol in `AGENTS.md`.

| | |
|---|---|
| Milestone | M0: Scaffold and guards (branch `milestone/M0`) |
| Depends on | none |
| Read first | SPEC §1 |
| Allowed to modify | `pyproject.toml`, `uv.lock`, `Makefile`, `init.sh`, `.env.example`, `src/cre_brain/**`, `tests/**`, `.pre-commit-config.yaml`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Sealed paths (see AGENTS.md), other tasks' entries, existing tests' assertions |

## Goal
Create the Python 3.12 project skeleton exactly as laid out in SPEC §1.

## Acceptance criteria
- [ ] AC1: `pyproject.toml` uses uv, defines package `cre_brain` and the `cre` Typer entry point, and pins exact versions
- [ ] AC2: ruff, mypy (strict on `src/`), pytest and hypothesis are configured; `make check` runs lint, types, tests and guards
- [ ] AC3: `init.sh` is idempotent: uv sync, creates `.local/`, installs pre-commit
- [ ] AC4: Empty subpackages exist for every directory in SPEC §1, each with `__init__.py`
- [ ] AC5: `uv run cre --help` prints the CLI help
- [ ] AC6: `.env.example` lists every env var name from AGENTS.md, with no values
- [ ] `make check` passes.

## Verify (must exit 0, paste the tail into PROGRESS.md)
```bash
./init.sh && make check && uv run cre --help
```

## Done when
All ACs are met, verify exits 0, `passes` for T001 is set to true, the task branch is merged into `milestone/M0`, and a PROGRESS.md entry is written. If blocked, write a BLOCKED entry with evidence and move on.
