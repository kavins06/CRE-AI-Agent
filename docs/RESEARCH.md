# RESEARCH: sources behind the decisions

> The product is an autonomous CRE acquisition analyst, "the Devin of real estate". These are the sources the method is based on (researched 2026-10-04). Items marked [secondary] were read through summaries because the primary page was blocked.

## Agent architecture
- Anthropic, "Building effective agents" (workflows vs. agents; evaluator-optimizer): https://www.anthropic.com/research/building-effective-agents
- Anthropic, "Effective context engineering for AI agents": https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
- Anthropic, "Writing tools for agents": https://www.anthropic.com/engineering/writing-tools-for-agents
- Anthropic, "Effective harnesses for long-running agents" (feature list, progress file, one feature per session): https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents
- Anthropic, "Harness design for long-running application development" (planner/generator/evaluator): https://www.anthropic.com/engineering/harness-design-long-running-apps
- Anthropic, multi-agent research system: https://www.anthropic.com/engineering/multi-agent-research-system
- Claude Agent SDK docs: https://code.claude.com/docs/en/agent-sdk/python, https://code.claude.com/docs/en/agent-sdk/hosting
- Cognition, "Don't build multi-agents" (share full context; single accountable agent) [secondary]
- Manus, "Context engineering for AI agents" (KV-cache, todo recitation, file system as memory, keep errors) [secondary]
- OpenAI, "Harness engineering" (AGENTS.md as a map; rules enforced in CI) [secondary]
- Agent Skills open standard: https://agentskills.io
- AGENTS.md standard: https://agents.md

## Self-improvement
- Karpathy, autoresearch: https://github.com/karpathy/autoresearch (program.md, keep/revert, results.tsv)
- GEPA (reflective prompt evolution; Pareto selection): https://arxiv.org/abs/2507.19457, https://github.com/gepa-ai/gepa
- ACE, Agentic Context Engineering (incremental playbooks; context collapse): https://arxiv.org/abs/2510.04618
- Agent Workflow Memory: https://arxiv.org/abs/2409.07429
- DAgger (expert corrections on learner-visited states): https://proceedings.mlr.press/v15/ross11a.html
- Darwin Gödel Machine (a cautionary case of an agent gaming a visible checker): https://arxiv.org/abs/2505.22954
- METR, reward hacking in frontier models (43x more frequent when the scorer is visible): https://metr.org/blog/2025-06-05-recent-reward-hacking/
- Shumailov et al., model collapse under recursive training: https://www.nature.com/articles/s41586-024-07566-y

## Evaluation
- Hamel Husain & Shreya Shankar, evals FAQ (error analysis, judge calibration): https://hamel.dev/blog/posts/evals-faq/
- Finance Agent Benchmark (expert rubrics; LLMs weak at multi-step financial calculation): https://arxiv.org/abs/2508.00828
- FinanceBench: https://arxiv.org/abs/2311.11944
- SpreadsheetBench: https://github.com/RUCKBReasoning/SpreadsheetBench
- OpenAI GDPval (expert-graded deliverables; instruction-following failures): https://openai.com/index/gdpval/
- Rubrics as Rewards: https://arxiv.org/abs/2507.17746
- PoLL, a panel of LLM judges: https://arxiv.org/abs/2404.18796

## CRE landscape (lessons)
- Archer: "AI for extraction, deterministic rules for mapping and math": https://www.archer.re/blog/ai-multifamily-underwriting-guide
- Others reviewed: Clik.ai, Cactus, Keyway, Dealpath AI, Hebbia, Blooma, AcquiOS, A.CRE AI tools. None demonstrates autonomous end-to-end diligence.

## Tools
- Jev (TypeSafe AI) System One model: https://typesafe.ai/blog/introducing-system-one-models-and-jev, PyPI `typesafe-sdk`
- GoRules ZEN: https://github.com/gorules/zen
- Docling: https://github.com/docling-project/docling
- pyxirr: https://github.com/Anexen/pyxirr
- DBOS: https://github.com/dbos-inc/dbos-transact-py
- inspect-ai: https://github.com/UKGovernmentBEIS/inspect_ai
- LiteLLM PyPI compromise (March 2026): https://docs.litellm.ai/blog/security-update-march-2026
