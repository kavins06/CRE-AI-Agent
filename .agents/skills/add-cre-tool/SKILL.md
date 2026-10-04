---
name: add-cre-tool
description: Add a new tool to the CRE analyst's in-process tool server (finance, Excel, rules, state, research) with tests and a FakeRunner transcript.
---
# Add a CRE tool

1. Put the logic in the right deterministic module under `src/cre_brain/` (finance/, excel/, rules/, data/, state/). **No arithmetic in prompts or LLM calls.**
2. Expose it in `src/cre_brain/runner/tools/` with the SDK `@tool` decorator (see `docs/LIBRARY_NOTES.md`):
   - The name is snake_case and namespaced by area, e.g. `finance_run`, `excel_build`.
   - Inputs form a small typed schema.
   - Output is concise JSON. Errors must say how to fix the call.
3. Register it with the `cre` SDK MCP server and add it to `allowed_tools` in the runner config.
4. If it has external side effects, it must check the user's toggle (SPEC §10.3) and default to drafting into `outbox/`.
5. Tests:
   - unit tests in `tests/runner/test_tools_<name>.py`
   - one FakeRunner transcript in `tests/fixtures/transcripts/` that exercises the tool
6. Document the tool in `docs/SPEC.md` §10.4 in the same PR.
