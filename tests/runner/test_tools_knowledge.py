import json
from pathlib import Path
from tempfile import TemporaryDirectory

from tests.runner.test_tools_t032 import tools

from cre_brain.knowledge import CacheStore, KnowledgeLibrary
from cre_brain.runner.tools.registry import CORE_TOOLS
from cre_brain.runner.tools.transport import handle_message

assert tools


def test_knowledge_tool_is_host_injected_and_never_writes_facts(tools) -> None:
    registry, _ = tools
    assert "knowledge_search" not in CORE_TOOLS
    assert "knowledge_search" not in registry.tool_models
    with TemporaryDirectory(prefix="analyst-library-") as directory:
        provider = KnowledgeLibrary(cache=CacheStore(Path(directory) / "public-knowledge"))
        registry.knowledge_provider = provider
        response = registry.call("knowledge_search", {"query": "NOI underwriting"})
        assert response["status"] == "ok", response
        hits = response["data"]["hits"]
        assert hits
        assert all(h["evidence_role"] == "public_reference_not_deal_fact" for h in hits)
        assert all(h["text"] is None for h in hits)
        assert all(h["scope"] == "global_public" for h in hits)
        assert registry.clone().knowledge_provider is provider
        with registry.transaction() as state:
            assert all(e.payload.get("binding") != "fact" for e in state.history())
        listed = handle_message(registry, {"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        assert "knowledge_search" in json.dumps(listed)


def test_knowledge_tool_rejects_tenant_scope_and_extraction_role(tools) -> None:
    registry, _ = tools
    with TemporaryDirectory(prefix="analyst-library-") as directory:
        registry.knowledge_provider = KnowledgeLibrary(
            cache=CacheStore(Path(directory) / "public-knowledge")
        )
        assert (
            registry.call("knowledge_search", {"query": "NOI", "scope": "deal"})["status"]
            == "refused"
        )
        assert (
            registry.call("knowledge_search", {"query": "NOI", "url": "https://example.com"})[
                "status"
            ]
            == "refused"
        )
        scoped = registry.clone(
            context=registry.context.model_copy(
                update={"role": "extraction", "session_id": "extract-session"}
            )
        )
        assert scoped.call("knowledge_search", {"query": "NOI"})["category"] == "unauthorized_role"
