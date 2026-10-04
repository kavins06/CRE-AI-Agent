# Platform decision: ii-agent

**Status:** candidate; not adopted or installed as the project runtime.
**Assessment date:** October 3, 2026 (America/New_York).
**Inspected version:** [Intelligent-Internet/ii-agent at 28563d6b738ac24df2c52048bd950afd7db4f4b7](https://github.com/Intelligent-Internet/ii-agent/tree/28563d6b738ac24df2c52048bd950afd7db4f4b7).
**Evidence scope:** source and documentation inspection. No deployment, performance benchmark, or recovery test was run.

## Decision to make

Determine whether ii-agent gets us to a working, teachable acquisition analyst faster and with acceptable maintenance cost compared with building on the Python/Pydantic AI baseline. The autonomous analyst and automated learning objectives in [METHOD.md](../METHOD.md) remain unchanged.

## Observed capabilities and project fit

| Capability inspected | Potential use | Remaining project responsibility |
|---|---|---|
| Web search and page-extraction tools | Public-source discovery and research | Source lineage, authority, date/version tracking, contradictions, and knowledge promotion |
| Custom prompts, tools, hooks, and model adapters | Configure analyst execution and connect finance tools | CRE-specific workflow, policy, correct calculations, and output validation |
| Skills framework | Load and execute reusable procedures | Curriculum, generating improvements, selection tests, and controlled releases |
| User interface, files, and user-input mechanisms | Owner teaching and inspection of work | Structured corrections, reviewed examples, and evaluation labels |
| Database-backed sessions and run continuation | Persist execution history and resume supported work | Canonical deal state, evidence revision semantics, consistent output regeneration, and recovery validation |
| Sandbox integrations | Isolate appropriate execution tasks | Explicit permissions, budgets, and separation of candidates from deployed releases |

Supporting source locations:

- [Agent factory and extension parameters](https://github.com/Intelligent-Internet/ii-agent/blob/28563d6b738ac24df2c52048bd950afd7db4f4b7/src/ii_agent/agents/factory/agent.py).
- [Core agent, tool hooks, and session interfaces](https://github.com/Intelligent-Internet/ii-agent/blob/28563d6b738ac24df2c52048bd950afd7db4f4b7/src/ii_agent/agents/agent.py).
- [Database session store](https://github.com/Intelligent-Internet/ii-agent/blob/28563d6b738ac24df2c52048bd950afd7db4f4b7/src/ii_agent/agents/sessions/store.py).
- [Skill creation interface](https://github.com/Intelligent-Internet/ii-agent/blob/28563d6b738ac24df2c52048bd950afd7db4f4b7/src/ii_agent/agents/skills/base.py).
- [README and documented deployment](https://github.com/Intelligent-Internet/ii-agent/blob/28563d6b738ac24df2c52048bd950afd7db4f4b7/README.md).

The inspected agent, skill, and documentation modules did not establish an existing curriculum scheduler, GEPA-style improvement process, or independent learning-release system. Skill loading and persistent conversation history do not themselves implement those functions. This is a scoped finding, not an exhaustive claim about every related upstream project.

## Adoption conditions

1. **Component licensing:** the top-level project is labeled Apache-2.0, but bundled XLSX, PDF, DOCX, and PPTX skills have separate restrictive license files. The inspected [XLSX license](https://github.com/Intelligent-Internet/ii-agent/blob/28563d6b738ac24df2c52048bd950afd7db4f4b7/src/ii_agent/agents/skills/builtin/xlsx/LICENSE.txt) restricts copying, derivative works, and distribution. Clarify applicable rights or replace affected components; do not assume the top-level license covers them.
2. **Runtime scope:** choose one primary agent loop. If ii-agent is selected, it replaces the Pydantic AI baseline for that role unless a separate use is justified.
3. **Portable domain services:** keep financial calculations, source/deal schemas, policy, training cases, and evaluator definitions independent of ii-agent's UI and session format.
4. **Independent learning process:** the experiment runner calls the chosen runtime as a candidate under test. It owns experiment records and release decisions; candidates cannot rewrite their evaluation criteria.
5. **Operational fit:** measure the cost of adapting and operating the platform, including its frontend, backend, database/storage, sandbox services, and unrelated product features. Broad functionality is useful only where its maintenance is justified.

## Representative integration trial

Use the same permitted model, packet, finance tools, and task criteria as the baseline where feasible. Record integration effort and full run cost rather than comparing appearance alone.

| Trial | Evidence required |
|---|---|
| Analyze a real rent roll and T-12 | Correct tool-mediated calculations and source-linked facts |
| Research a missing underwriting question | Preserved evidence with date, jurisdiction, uncertainty, and applicability |
| Produce a workbook and recommendation | Inspectable, consistent artifacts using components we may use |
| Receive an expert correction | A structured teaching record rather than only another chat message |
| Test an improvement | Candidate version, baseline comparison, separate evaluation case, and recorded acceptance/rejection |
| Interrupt and revise | Successful recovery and complete propagation of a document change into affected outputs |

Adopt if this trial demonstrates useful acceleration and acceptable maintenance, with the component-license issue resolved. Retain the lighter baseline if integrating our domain controls and learning system requires disproportionate platform changes.

## Relationship to Karpathy-style autoresearch

The learning method is already specified in METHOD.md section 7 and supported by research reference R14. ii-agent is a possible execution environment for those experiments. It does not eliminate the need to build the learning charter, scheduler, candidate isolation, evaluator, experiment records, release process, and rollback.

Implementation status remains documentation only. A working ii-agent chat session would demonstrate a platform installation; the completion demonstration in section 7 is what establishes an automated improvement loop.
