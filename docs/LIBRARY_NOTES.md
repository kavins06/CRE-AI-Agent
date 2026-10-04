# LIBRARY NOTES: pinned versions, verified snippets, gotchas

> The product is an autonomous CRE acquisition analyst. This is the reference for the libraries it is built on.

Versions were checked on PyPI on 2026-10-04.
- **Pin exact versions** in `pyproject.toml`. Upgrade only in a dedicated task.
- Items marked **[verify]** must be confirmed against the installed package in task T030 (the Agent SDK spike) or the task that first uses them. Record what you find in PROGRESS.md and correct this file in the same PR.

## claude-agent-sdk (Python), `pip install claude-agent-sdk`
- Docs: https://code.claude.com/docs/en/agent-sdk/python and https://code.claude.com/docs/en/agent-sdk/hosting
- **Requirements:**
  - Python ≥3.10
  - it runs the Claude Code CLI as a subprocess, so the box needs the CLI runtime (Node.js) [verify the install method]
  - one subprocess per session; budget about 1 GiB RAM per agent
- **Model support:** Claude models only (Anthropic API, or Bedrock/Vertex/Foundry). This is why we use the `Runner` abstraction.
- **What it provides:** the agent loop; built-in file/bash/web tools; subagents; automatic compaction; Skills; hooks (PreToolUse, PostToolUse, UserPromptSubmit, PreCompact, SubagentStart/Stop and others); in-process tools through an SDK MCP server; external MCP servers; sessions, resume and fork; permission modes; structured output; OpenTelemetry support.

```python
from claude_agent_sdk import (ClaudeSDKClient, ClaudeAgentOptions, tool,
                              create_sdk_mcp_server, HookMatcher, AgentDefinition)

@tool("finance_run", "Run a deterministic finance function", {"fn": str, "args": dict})
async def finance_run(args):
    result = ...  # call cre_brain.finance
    return {"content": [{"type": "text", "text": result.model_dump_json()}]}

cre = create_sdk_mcp_server(name="cre", version="1.0.0", tools=[finance_run])

async def policy_hook(input_data, tool_use_id, context):
    if violates_policy(input_data):
        return {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                "permissionDecision": "deny", "permissionDecisionReason": "toggle off: email"}}
    return {}

options = ClaudeAgentOptions(
    model="claude-opus-5-5", cwd="/home/agent/deals/D1",
    mcp_servers={"cre": cre},
    allowed_tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep", "WebFetch", "Skill",
                   "mcp__cre__finance_run"],
    hooks={"PreToolUse": [HookMatcher(matcher=None, hooks=[policy_hook])]},
    agents={"rentroll_extractor": AgentDefinition(
        description="Extract rent roll facts", prompt=open("brain/prompts/extract_rentroll.md").read(),
        tools=[], model="sonnet")},
    setting_sources=["project"],      # loads .claude/skills  [verify]
    max_turns=200,
)
async with ClaudeSDKClient(options=options) as client:
    await client.query("Screen this deal and draft broker questions.")
    async for msg in client.receive_response():
        emit_event(msg)
```

**[verify] items:**
- the exact name and shape of the structured-output option (`output_format` with a JSON schema)
- per-subagent model aliases vs. full IDs
- how Skills are enabled (`setting_sources` plus the `Skill` tool)
- the cost and budget option names
- the hook callback signature and the deny payload shape
- the session resume API

**Gotchas:**
- Keep the system prompt prefix stable so prompt caching works.
- Never put raw seller documents into the lead agent's context.
- Tool results should be concise JSON.

## GEPA, `gepa` 0.1.4 (2026-07-15); dspy 3.4.0
- The PyPI release may lag `main`. Use the API of the pinned version [verify `optimize_anything` config class names].

```python
from gepa.optimize_anything import optimize_anything, GEPAConfig, EngineConfig
import gepa.optimize_anything as oa
def evaluate(candidate: str, example) -> tuple[float, dict]:
    score, categories = run_fixture(candidate, example)   # categories only, never rubric text
    oa.log("; ".join(categories))
    return score, {"feedback": "; ".join(categories)}
res = optimize_anything(seed_candidate=current_text, evaluator=evaluate, dataset=train, valset=dev,
                        objective="Improve IC memo quality without violating counter-metrics",
                        config=GEPAConfig(engine=EngineConfig(max_metric_calls=40)))
```

Higher is better. Score a failed example as 0; never raise.

## inspect-ai 0.3.276
```python
from inspect_ai import Task, task, eval
from inspect_ai.dataset import Sample
from inspect_ai.scorer import scorer, Score, Target, accuracy, stderr, CORRECT, INCORRECT
@scorer(metrics=[accuracy(), stderr()])
def field_accuracy(): ...
@task
def screen_suite(): return Task(dataset=[Sample(input=..., target=...)], solver=..., scorer=field_accuracy())
logs = eval(screen_suite(), model="anthropic/claude-sonnet-5-5")
```
- The default log format is `.eval`. Read logs with `inspect_ai.log.read_eval_log`.
- For agent runs, write a custom solver that calls our `Runner` and returns the deliverables.

## docling 2.133.0
```python
from docling.document_converter import DocumentConverter
doc = DocumentConverter().convert(path).document
for t in doc.tables:
    df = t.export_to_dataframe(doc=doc); prov = t.prov[0]  # prov.page_no, prov.bbox (check coord_origin)
```
- PDF bbox origin is often BOTTOMLEFT. Normalize with `to_top_left_origin(page_height)`.
- **Never send native XLSX/CSV through docling.** Read them with openpyxl or pandas.

## zen-engine 2.1.2 (GoRules)
```python
import zen
engine = zen.ZenEngine({"loader": lambda key: open(f"src/cre_brain/rules/tables/{key}").read()})
out = engine.evaluate("buy_box.default.json", {"units": 120, "dscr": 1.31, "market_tier": "B"})
```
- JDM structure: `nodes` (`inputNode`, `decisionTableNode`, `outputNode`) + `edges`.
- Decision-table `hitPolicy` is `first` or `collect`.
- Result keys beyond `result` and the trace option are [verify].

## pyxirr 0.10.8
- `xirr(dates, amounts)`, `irr(cfs)`, `pmt(rate, nper, pv)` (returns a negative number).
- **`npv(r, cfs)` defaults to numpy semantics** (discounting starts at period 0). Use `npv(r, cfs, start_from_zero=False)` to match Excel's `=NPV`.
- Returns `None` when there is no solution (with `silent=True`). Handle that explicitly.

## LibreOffice headless recalculation
`soffice --convert-to xlsx` does **not** reliably recalculate. Use a Basic macro installed in a dedicated profile:
```basic
Sub RecalculateAndSave()
  ThisComponent.calculateAll() : ThisComponent.store() : ThisComponent.close(True)
End Sub
```
```bash
timeout 60 soffice --headless --norestore -env:UserInstallation=file:///tmp/lo_profile_$$ \
  "vnd.sun.star.script:Standard.Module1.RecalculateAndSave?language=Basic&location=application" /abs/model.xlsx
```
- Then run `openpyxl.load_workbook(path, data_only=True)`.
- **Assert that the values are not `None`.** A no-op run can still exit 0.
- Use one profile per worker.
- Never save a workbook loaded with `data_only=True`.
- [verify the exact macro install path inside the box image]

## DBOS 3.2.0
```python
from dbos import DBOS
DBOS(config={"name": "cre", "system_database_url": os.environ["DBOS_DATABASE_URL"]})  # sqlite:/// in dev
@DBOS.step()
def run_segment(...): ...
@DBOS.workflow()
def task_workflow(task_id: str): ...
DBOS.launch()
```
- A completed step is never re-run.
- Workflows must be deterministic.
- An uncaught exception puts the workflow in ERROR and it is not recovered, so use step retries for transient faults.

## typesafe-sdk 0.7.2 (Jev), verified from source
```python
from typesafe_sdk import TypeSafeClient, Choice, Score, Noul
with TypeSafeClient() as c:   # TYPESAFE_API_KEY env; default model jev-latest
    r = c.system_one(state={"text": doc_head},
        questions={"doc_type": Choice(instructions="Document type?",
                    criteria={"rent_roll": None, "t12": None, "om": None, "lease": None, "other": None})})
    r.choices["doc_type"].choice, r.choices["doc_type"].confidence
```
- `Score.criteria` is an ordered list. `Noul.criteria` uses the keys `"true"` and `"false"`.
- The default timeout is 10 s.
- Jev launched in September 2026. Keep it behind `DecisionModel` and use it only after calibrating on our labelled cases.

## Langfuse (optional, self-hosted)
- OTLP over HTTP to `$LANGFUSE_BASE_URL/api/public/otel`, with a Basic auth header built from the public and secret keys.
- Redact prompt and completion content for tenant data.

## Banned
- LiteLLM (2026 supply-chain compromise)
- HyperFormula (GPL/commercial, unless a licence is bought)
- Marker (GPL code, restricted model weights)
- ii-agent's bundled office skills (proprietary)
