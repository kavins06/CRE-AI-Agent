# T003: Config system and runner/role registry

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol and branch model in `AGENTS.md` (work on `dev`).

| | |
|---|---|
| Milestone | M0: Guards and scaffold |
| Depends on | T001 |
| Read first | SPEC §9 |
| Allowed to modify | `config/models.yaml`, `config/toggles.default.yaml`, `src/cre_brain/config/**`, `tests/config/**`, `config/budget.yaml`, `config/gates.yaml`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Anything else in `scripts/protected_paths.txt`; other tasks' entries; existing tests' assertions |
| Protected paths touched | Yes. The milestone PR needs the owner's `protected-change` label |

## Goal
Typed config with runner roles, budgets, gate tolerances, toggles. budget.yaml and gates.yaml are protected: create them here; later edits need the owner label.

## Acceptance criteria
Each ACn needs at least one passing, non-skipped test named `test_t003_ac<n>_*`.
- [ ] AC1 (`test_t003_ac1_*`): `models.yaml` (runner: codex; roles lead/extraction/verifier/classifier/reflection with profiles; model `<owner sets>`), `budget.yaml` (segment_max_min, nightly_sessions=200, nightly_wallclock_h=10, max_parallel_extractions=4, max_parallel_sessions=2, codex_login_max_concurrency=1, box_reconnect_s), `gates.yaml` (tolerances, Excel function whitelist, fragility_margin), `toggles.default.yaml` (off|ask|on, default off)
- [ ] AC2 (`test_t003_ac2_*`): `cre_brain.config.load()` returns validated settings; env overrides files
- [ ] AC3 (`test_t003_ac3_*`): `config.live_enabled(role)` checks `codex login status` (subprocess, mocked in tests) or SDK key; returns False cleanly
- [ ] AC4 (`test_t003_ac4_*`): A test fails if any model name string appears in `src/` outside the config package
- [ ] `make check` passes.

## Verify (must exit 0; paste the tail into PROGRESS.md)
```bash
uv run pytest tests/config -q && uv run python scripts/check_task.py T003
```

## Done when
All ACs are met, verify exits 0, `passes` for T003 is true, the task branch is merged into `dev` and pushed, and a PROGRESS.md entry is written. If you are blocked, write a BLOCKED entry with evidence and move on.
