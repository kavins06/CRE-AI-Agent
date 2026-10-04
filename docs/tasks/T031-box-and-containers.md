# T031: Local box, extraction container, OS enforcement

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol and branch model in `AGENTS.md` (work on `dev`).

| | |
|---|---|
| Milestone | M2: First working analyst (thin slice: SCREEN + UW_MODEL via cre run) |
| Depends on | T001 |
| Read first | SPEC §3, §10.2 |
| Allowed to modify | `src/cre_brain/sandbox/**`, `docker/**`, `tests/sandbox/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Anything else in `scripts/protected_paths.txt`; other tasks' entries; existing tests' assertions |
| Protected paths touched | No |

## Goal
SandboxProvider + reference images with OS-level limits.

## Acceptance criteria
Each ACn needs at least one passing, non-skipped test named `test_t031_ac<n>_*`.
- [ ] AC1 (`test_t031_ac1_*`): SandboxProvider protocol + LocalDockerProvider; `docker/box` and `docker/extract` images per SPEC §3/§10.2 (Codex auth injected at runtime, never baked)
- [ ] AC2 (`test_t031_ac2_*`): Analyst mount is only /home/agent/work; /srv/raw not mounted; non-root user; writable paths limited; egress via allowlist proxy (dev: a simple proxy container)
- [ ] AC3 (`test_t031_ac3_*`): Isolation tests with tool policy disabled: write outside allowed paths fails; curl to non-allowlisted domain fails; /srv/raw unreadable; user A cannot read user B; no box-to-box network
- [ ] AC4 (`test_t031_ac4_*`): `tests/sandbox/contract.py` runnable by the owner against their provider
- [ ] `make check` passes.

## Verify (must exit 0; paste the tail into PROGRESS.md)
```bash
uv run pytest tests/sandbox -q && uv run python scripts/check_task.py T031
```

## Done when
All ACs are met, verify exits 0, `passes` for T031 is true, the task branch is merged into `dev` and pushed, and a PROGRESS.md entry is written. If you are blocked, write a BLOCKED entry with evidence and move on.
