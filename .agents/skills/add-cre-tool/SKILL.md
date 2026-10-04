---
name: add-cre-tool
description: Add a new tool to the CRE analyst's in-process tool server (finance, Excel, rules, state, research) with tests and a FakeRunner transcript.
---
# Add a CRE tool

1. Put the logic in the right deterministic module under `src/cre_brain/` (finance/, excel/, rules/, data/, state/). **No arithmetic in prompts or LLM calls.**
2. Register it once in `src/cre_brain/runner/tools/registry.py`. The registry exposes it both through the `cre` MCP server (`cre mcp serve`) and as `cre tool <name>`:
   - The name is snake_case and namespaced by area, e.g. `finance_run`, `excel_build`.
   - Inputs form a small typed schema.
   - Output is concise JSON. Errors must say how to fix the call.
3. If the tool needs approval settings, add it to the Codex MCP config template (`templates/codex/config.toml`).
4. If it has external side effects, it must call `policy.check_toggle` (SPEC §10.3), default to drafting into `outbox/`, and **never block**. With `ask`, return `pending_confirmation`.
5. Tests:
   - unit tests in `tests/runner/test_tools_<name>.py`
   - name the tests `test_<task>_ac<n>_*`
   - FakeRunner plumbing coverage only from `cre record` transcripts, never hand-written ones
6. Document the tool in `docs/SPEC.md` §10.4 in the same PR.
