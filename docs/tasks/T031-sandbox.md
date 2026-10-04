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
- [ ] AC2: `docker/box/Dockerfile` satisfies the SPEC §3 image contract (Python, cre_brain, Codex CLI, LibreOffice + macro, Chromium/Playwright); Codex auth is mounted/injected by the owner setup, never baked in
- [ ] AC3: Workspace layout created on `create()`; `resume()` preserves disk
- [ ] AC4: OS-level enforcement per SPEC §3: non-root agent user, read-only firms/, writable only deals/ outbox/ memory/ scratch, egress allowlist proxy
- [ ] AC5: Isolation tests with all tool policy disabled: shell write outside allowed paths fails; curl to non-allowlisted domain fails; user A cannot read user B; no box-to-box network; secrets absent from snapshot
- [ ] AC6: A contract test suite the owner can run against their own provider (`tests/sandbox/contract.py`)
- [ ] `make check` passes.

## Verify (must exit 0, paste the tail into PROGRESS.md)
```bash
uv run pytest tests/sandbox -q
```

## Done when
All ACs are met, verify exits 0, `passes` for T031 is set to true, the task branch is merged into `milestone/M3`, and a PROGRESS.md entry is written. If blocked, write a BLOCKED entry with evidence and move on.
