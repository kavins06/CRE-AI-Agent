# T003: Config system and model-role registry

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol in `AGENTS.md`.

| | |
|---|---|
| Milestone | M0: Scaffold and guards (branch `milestone/M0`) |
| Depends on | T001 |
| Read first | SPEC §9 |
| Allowed to modify | `config/**`, `src/cre_brain/config/**`, `tests/config/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Sealed paths (see AGENTS.md), other tasks' entries, existing tests' assertions |

## Goal
Typed config loading with model roles, budgets, gate tolerances and toggles.

## Acceptance criteria
- [ ] AC1: `config/models.yaml` (runner: codex, roles with profiles), `budget.yaml` (incl. nightly_sessions, nightly_wallclock_h, max_parallel_extractions, max_parallel_sessions, box_reconnect_s), `gates.yaml`, `toggles.default.yaml` exist with SPEC §9 defaults; toggles are `off|ask|on`, default `off`
- [ ] AC2: `cre_brain.config.load()` returns validated Pydantic settings; env vars override the files
- [ ] AC3: `config.live_enabled(role)` returns true only if the role's runner is usable (Codex CLI installed and `codex login status` succeeds, or the SDK key is present for later runners); callers log `SKIPPED_NO_RUNNER`
- [ ] AC4: No model ID appears anywhere in `src/` outside the config package (enforced by a test that greps for it)
- [ ] `make check` passes.

## Verify (must exit 0, paste the tail into PROGRESS.md)
```bash
uv run pytest tests/config -q
```

## Done when
All ACs are met, verify exits 0, `passes` for T003 is set to true, the task branch is merged into `milestone/M0`, and a PROGRESS.md entry is written. If blocked, write a BLOCKED entry with evidence and move on.
