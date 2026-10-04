# T070: Connector interfaces, toggles and stubs

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol in `AGENTS.md`.

| | |
|---|---|
| Milestone | M6: Connectors and portability (branch `milestone/M6`) |
| Depends on | T033 |
| Read first | SPEC §2; METHOD §3.6 |
| Allowed to modify | `src/cre_brain/connectors/**`, `tests/connectors/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Sealed paths (see AGENTS.md), other tasks' entries, existing tests' assertions |

## Goal
Ready-to-plug interfaces for the owner's connectors.

## Acceptance criteria
- [ ] AC1: EmailConnector, DataRoomConnector, MarketDataProvider (Public impl + CoStar/YardiMatrix/Trepp stubs), DocumentStore and Notifier, each with a contract test suite
- [ ] AC2: Per-user toggles API; all default off; stubs write to outbox/
- [ ] `make check` passes.

## Verify (must exit 0, paste the tail into PROGRESS.md)
```bash
uv run pytest tests/connectors -q
```

## Done when
All ACs are met, verify exits 0, `passes` for T070 is set to true, the task branch is merged into `milestone/M6`, and a PROGRESS.md entry is written. If blocked, write a BLOCKED entry with evidence and move on.
