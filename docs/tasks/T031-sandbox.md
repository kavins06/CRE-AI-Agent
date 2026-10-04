# T031: User computer: SandboxProvider + local Docker box

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol in `AGENTS.md`.

| | |
|---|---|
| Milestone | M3: Agent (branch `milestone/M3`) |
| Depends on | T001 |
| Read first | SPEC §3 |
| Allowed to modify | `src/cre_brain/sandbox/**`, `docker/box/**`, `tests/sandbox/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Sealed paths (see AGENTS.md), other tasks' entries, existing tests' assertions |

## Goal
The per-user computer interface, the reference image and isolation tests.

## Acceptance criteria
- [ ] AC1: `SandboxProvider` protocol per SPEC §2; `LocalDockerProvider` implementation
- [ ] AC2: `docker/box/Dockerfile` satisfies the SPEC §3 image contract (Python, cre_brain, Agent SDK runtime, LibreOffice + macro, Chromium/Playwright)
- [ ] AC3: Workspace layout created on `create()`; `resume()` preserves disk
- [ ] AC4: Isolation tests: user A cannot read user B; no box-to-box network; secrets absent from snapshot
- [ ] AC5: A contract test suite the owner can run against their own provider (`tests/sandbox/contract.py`)
- [ ] `make check` passes.

## Verify (must exit 0, paste the tail into PROGRESS.md)
```bash
uv run pytest tests/sandbox -q
```

## Done when
All ACs are met, verify exits 0, `passes` for T031 is set to true, the task branch is merged into `milestone/M3`, and a PROGRESS.md entry is written. If blocked, write a BLOCKED entry with evidence and move on.
