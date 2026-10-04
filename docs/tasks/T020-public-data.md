# T020: Public data clients with cache and fixtures

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol in `AGENTS.md`.

| | |
|---|---|
| Milestone | M2: Data and evals (branch `milestone/M2`) |
| Depends on | T003 |
| Read first | DATA_SOURCES.md |
| Allowed to modify | `src/cre_brain/data/**`, `tests/data/**`, `tests/fixtures/data/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Sealed paths (see AGENTS.md), other tasks' entries, existing tests' assertions |

## Goal
Rate-limited, cached clients for EDGAR, FRED, ACS, HUD, BLS and Cook County.

## Acceptance criteria
- [ ] AC1: One module per source with typed responses; EDGAR sends `SEC_USER_AGENT` and is limited to 8 requests/second
- [ ] AC2: Disk cache keyed by URL+params with TTL; recorded HTTP fixtures (e.g. vcrpy) so tests run offline
- [ ] AC3: Missing key → clean skip with `SKIPPED_NO_KEY`
- [ ] AC4: Field names marked [U] in DATA_SOURCES are verified against live responses when keys exist; the findings are recorded in PROGRESS.md and DATA_SOURCES.md is updated
- [ ] AC5: `cre data pull <source> ...` CLI
- [ ] `make check` passes.

## Verify (must exit 0, paste the tail into PROGRESS.md)
```bash
uv run pytest tests/data -q
```

## Done when
All ACs are met, verify exits 0, `passes` for T020 is set to true, the task branch is merged into `milestone/M2`, and a PROGRESS.md entry is written. If blocked, write a BLOCKED entry with evidence and move on.
