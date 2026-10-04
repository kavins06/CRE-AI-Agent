# T034: Quarantined extraction pipeline

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol in `AGENTS.md`.

| | |
|---|---|
| Milestone | M3: Agent (branch `milestone/M3`) |
| Depends on | T033, T011 |
| Read first | SPEC §10.2; LIBRARY_NOTES docling |
| Allowed to modify | `src/cre_brain/extraction/**`, `brain/prompts/extract_*.md`, `tests/extraction/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Sealed paths (see AGENTS.md), other tasks' entries, existing tests' assertions |

## Goal
Parse documents and extract typed facts through quarantined, read-only Codex sessions.

## Acceptance criteria
- [ ] AC1: Native XLSX/CSV cell reader; Docling PDF parsing with page/bbox anchors (origin normalized); optional Reducto adapter
- [ ] AC2: Per-document one-shot `codex exec --profile extractor --sandbox read-only` (no MCP servers, network off) with `--output-schema` per document type; input is only the pre-parsed file; outputs → `Fact`s (`SELLER_ASSERTION`) with provenance; parallel up to `max_parallel_extractions`
- [ ] AC3: Coverage and checksum gates run on the extracted facts
- [ ] AC4: Scores ≥95% critical-field accuracy on synthetic set A (FakeRunner transcripts in CI; live when a key exists)
- [ ] `make check` passes.

## Verify (must exit 0, paste the tail into PROGRESS.md)
```bash
uv run pytest tests/extraction -q
```

## Done when
All ACs are met, verify exits 0, `passes` for T034 is set to true, the task branch is merged into `milestone/M3`, and a PROGRESS.md entry is written. If blocked, write a BLOCKED entry with evidence and move on.
