# T042: Box agent (cre-boxd) and control-plane link

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol in `AGENTS.md`.

| | |
|---|---|
| Milestone | M3: Agent (branch `milestone/M3`) |
| Depends on | T031, T030, T033 |
| Read first | SPEC §10.8 |
| Allowed to modify | `src/cre_brain/sandbox/boxd/**`, `tests/sandbox/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Sealed paths (see AGENTS.md), other tasks' entries, existing tests' assertions |

## Goal
The in-box service that runs analyst sessions and talks outbound to the control plane.

## Acceptance criteria
- [ ] AC1: `cre-boxd` connects outbound over authenticated WebSocket; no inbound ports
- [ ] AC2: Commands: idempotent start_or_attach(task_id, segment_no), interrupt, pause, resume, deliver_message, sync_playbook
- [ ] AC3: Events streamed with seq, acked, re-sent after reconnect, de-duplicated by (task_id, seq); heartbeats; unreachable handling
- [ ] AC4: Box-disk-loss recovery: fresh box rebuilt from state DB + todo snapshot, new segment with recovery message (test)
- [ ] AC5: Stuck detector and redaction run in the box agent on the event stream
- [ ] `make check` passes.

## Verify (must exit 0, paste the tail into PROGRESS.md)
```bash
uv run pytest tests/sandbox -q -k boxd
```

## Done when
All ACs are met, verify exits 0, `passes` for T042 is set to true, the task branch is merged into `milestone/M3`, and a PROGRESS.md entry is written. If blocked, write a BLOCKED entry with evidence and move on.
