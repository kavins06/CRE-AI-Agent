# T035: Quarantined extraction to facts

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol and branch model in `AGENTS.md` (work on `dev`).

| | |
|---|---|
| Milestone | M2: First working analyst (thin slice: SCREEN + UW_MODEL via cre run) |
| Depends on | T033, T034, T012 |
| Read first | SPEC §10.2 |
| Allowed to modify | `src/cre_brain/extraction/**`, `brain/prompts/extract_*.md`, `evals/schemas/**`, `tests/extraction/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Anything else in `scripts/protected_paths.txt`; other tasks' entries; existing tests' assertions |
| Protected paths touched | Yes. The milestone PR needs the owner's `protected-change` label |

## Goal
One throwaway container per document, schema output → Facts.

## Acceptance criteria
Each ACn needs at least one passing, non-skipped test named `test_t035_ac<n>_*`.
- [ ] AC1 (`test_t035_ac1_*`): Per-doc `codex exec -p extractor --output-schema` in docker/extract with only the parsed file mounted, no MCP (separate CODEX_HOME), network restricted
- [ ] AC2 (`test_t035_ac2_*`): Schema per doc type (rent roll, T-12, OM summary); output → Facts (SELLER_ASSERTION) with provenance; parallel up to max_parallel_extractions
- [ ] AC3 (`test_t035_ac3_*`): Coverage + checksum gates run after extraction (deterministic)
- [ ] AC4 (`test_t035_ac4_*`): Plumbing tested via FakeRunner; quality is NOT claimed here (measured in T041)
- [ ] `make check` passes.

## Verify (must exit 0; paste the tail into PROGRESS.md)
```bash
uv run pytest tests/extraction -q && uv run python scripts/check_task.py T035
```

## Done when
All ACs are met, verify exits 0, `passes` for T035 is true, the task branch is merged into `dev` and pushed, and a PROGRESS.md entry is written. If you are blocked, write a BLOCKED entry with evidence and move on.
