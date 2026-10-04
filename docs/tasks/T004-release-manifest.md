# T004: Brain Release manifest

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol in `AGENTS.md`.

| | |
|---|---|
| Milestone | M0: Scaffold and guards (branch `milestone/M0`) |
| Depends on | T003 |
| Read first | LEARNING §7 |
| Allowed to modify | `src/cre_brain/release/**`, `tests/release/**`, `brain/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Sealed paths (see AGENTS.md), other tasks' entries, existing tests' assertions |

## Goal
Hash-identified, replayable releases of the brain.

## Acceptance criteria
- [ ] AC1: `brain/` exists with `skills/`, `prompts/` and `playbook/global.md` placeholders
- [ ] AC2: `cre release build` writes `releases/<hash>.json` covering brain/, config/*.yaml, the gates code hash and the model IDs
- [ ] AC3: `cre release list` and `cre release rollback <hash>` work against a local registry
- [ ] AC4: Tests: changing one byte in brain/ changes the hash; rollback restores the files
- [ ] `make check` passes.

## Verify (must exit 0, paste the tail into PROGRESS.md)
```bash
uv run pytest tests/release -q
```

## Done when
All ACs are met, verify exits 0, `passes` for T004 is set to true, the task branch is merged into `milestone/M0`, and a PROGRESS.md entry is written. If blocked, write a BLOCKED entry with evidence and move on.
