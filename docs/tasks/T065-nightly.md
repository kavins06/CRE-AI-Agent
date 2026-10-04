# T065: Releases, rollback and nightly run

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol in `AGENTS.md`.

| | |
|---|---|
| Milestone | M5: Learning loop (branch `milestone/M5`) |
| Depends on | T004, T062, T063 |
| Read first | LEARNING §7, §8 |
| Allowed to modify | `learning/nightly.py`, `src/cre_brain/release/**`, `tests/learning/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Sealed paths (see AGENTS.md), other tasks' entries, existing tests' assertions |

## Goal
An unattended nightly improvement run with safe releases.

## Acceptance criteria
- [ ] AC1: `cre learn nightly` rotates deliverable kinds by gap to bar, respects `nightly_sessions`/`nightly_wallclock_h`, and writes a PR + PROGRESS entry
- [ ] AC2: Weekly end-to-end non-inferiority check; rollback tested
- [ ] `make check` passes.

## Verify (must exit 0, paste the tail into PROGRESS.md)
```bash
uv run pytest tests/learning -q -k nightly
```

## Done when
All ACs are met, verify exits 0, `passes` for T065 is set to true, the task branch is merged into `milestone/M5`, and a PROGRESS.md entry is written. If blocked, write a BLOCKED entry with evidence and move on.
