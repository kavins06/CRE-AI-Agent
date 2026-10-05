"""Recorder-generated synthetic replay only, never live analyst evidence."""

import pytest
from tests.runner.test_codex_t033 import build, collect, draft, raw

from cre_brain.knowledge import CacheStore, KnowledgeLibrary
from cre_brain.runner.fake import FakeRunner
from cre_brain.runner.record import record_segment

pytest_plugins = ("tests.runner.test_codex_t033",)


@pytest.mark.asyncio
async def test_t032_ac1_knowledge_replays_only_from_the_canonical_recorder(
    setup, public_probe_path
):
    registry, _, _, ws, seg = setup
    registry.knowledge_provider = KnowledgeLibrary(
        cache=CacheStore(public_probe_path / "public-knowledge")
    )
    draft(setup)
    lines = raw(
        {"type": "thread.started", "thread_id": "provider-session"},
        {"type": "turn.started"},
        {
            "type": "item.completed",
            "item": {
                "id": "knowledge-call",
                "type": "mcp_tool_call",
                "server": "cre",
                "tool": "knowledge_search",
                "arguments": {"query": "repayment capacity"},
                "result": {"content": [{"type": "text", "text": '{"status":"ok","data":{}}'}]},
                "status": "completed",
            },
        },
        {
            "type": "item.completed",
            "item": {
                "id": "final-call",
                "type": "mcp_tool_call",
                "server": "cre",
                "tool": "finalize_deliverable",
                "arguments": {"deliverable_id": "memo"},
                "result": {"content": [{"type": "text", "text": '{"status":"ok","data":{}}'}]},
                "status": "completed",
            },
        },
        {"type": "turn.completed", "usage": {"input_tokens": 1, "output_tokens": 1}},
    )
    runner, _ = build(setup, lines)
    output = public_probe_path / "synthetic-knowledge-capture"
    await record_segment(runner, seg, ws, registry.context, output, expected_deliverables=("memo",))
    events = await collect(
        FakeRunner(output, registry=registry),
        seg.model_copy(update={"segment_no": 1}),
        ws,
        registry.context,
    )
    assert any(
        e.kind == "tool_result" and e.payload.get("tool") == "knowledge_search" for e in events
    )
    assert events[-1].payload["plumbing_only"] is True
