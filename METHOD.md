# Blueprint: How to build the "brain" of an autonomous CRE Acquisition Analyst agent

**For:** the engineers or agent who will build it.
**Scope:** the brain only. UI/UX, integrations and the CRE domain content are owned by the user.

## What we are building and the constraints

| | |
|---|---|
| **Job** | Do everything an acquisition analyst does, from a received deal package to the finished deal file: screening, underwriting, due diligence, IC memo, LOI, deal-file QA |
| **Asset class** | Multifamily first. Other asset classes come later, each with its own skills and evals. |
| **Approach** | A **model-agnostic harness**. No fine-tuning of weights. Runs on any frontier API. |
| **Autonomy** | Fully autonomous in production. Each phase earns autonomy by passing a measured bar in shadow mode first. |
| **Data** | Almost none. One expert at about 10 h/week, books, and public sources. |
| **Language** | Python |
| **Underwriting output** | A Python model and a live-formula Excel model, cross-checked against each other |

**What "training" means here.** The brain is a set of versioned files that get improved against an evaluation suite:
- prompts
- skills (`SKILL.md`)
- a playbook
- decision tables
- tool code

This is the autoresearch idea applied to agent instructions instead of model code. Mapped to ordinary model training:
- **Weights:** the files above
- **Loss function:** the evaluation suite
- **Optimizer:** the autoresearch loop with GEPA

---

## 1. Frameworks and tools

| Need | Use | Why / notes |
|---|---|---|
| Agent framework | **Pydantic AI** | Typed outputs and native adapters for Anthropic, OpenAI and Google, so you can swap models freely. Durable-execution integrations. |
| Workflow durability | **DBOS + Postgres** in v1, **Temporal** in v2 | Phases checkpoint and resume. Move to Temporal once diligence events arrive over weeks. |
| Model gateway | Native SDKs through Pydantic AI. **Avoid LiteLLM.** | LiteLLM had a PyPI supply-chain compromise in March 2026. Gateways also lose prompt caching and thinking features. |
| Fast typed decisions | **Jev (TypeSafe AI)**, wrapped in a `DecisionModel` interface with an LLM fallback | Use it for document classification, routing and red-flag scoring. It is new (Sept 2026). Keep it off the critical path until thresholds are calibrated on real labelled cases. |
| Deterministic rules | **GoRules ZEN Engine (JDM decision tables)** | For the buy-box, policy bands for LOI terms, allowed assumption ranges and escalation policy. The expert edits these in its visual editor. |
| Document extraction | **Docling** (self-hosted, MIT) as the primary extractor. A frontier vision model as the second pass, only on high-value fields or failed checks. **Reducto** optional for hard scans. | Read native XLSX/CSV directly as cells and never send them through a vision model. |
| Finance math | **pyxirr** plus an in-house finance library, tested with `hypothesis` | The LLM never does arithmetic. Watch pyxirr's `npv` convention, which differs from Excel's. |
| Excel | **openpyxl** to fill the template, **LibreOffice headless** to recalculate it, then a cell-by-cell diff against Python | Restrict the template to a whitelist of functions and no circular references. Check each template once in real Excel in CI. Avoid HyperFormula (GPL/commercial licence) and Marker (licence restrictions). |
| Skills format | The **Agent Skills standard** (`SKILL.md`) | Portable across Claude, Codex and Gemini. Only loaded when needed. |
| Code sandbox | **E2B** or Docker+gVisor | Only for code the LLM writes. Trusted finance tools run outside it. |
| Evals | **Inspect AI** (or promptfoo) plus a custom synthetic deal generator | |
| Optimizers | **GEPA** (prompt and skill optimizer), **DSPy** (extraction signatures), **ACE pattern** (playbook) | |
| Observability | **OpenTelemetry**, sent to a self-hosted **Langfuse** | Deal data is under NDA, so self-host and redact. |
| Storage | Postgres, and S3 with a separate encryption key per deal | |

## 2. Architecture

**Shape.** A fixed workflow of phases, with an agent working inside each phase. This follows Anthropic's "workflows vs agents" guidance and Cognition's "Don't build multi-agents" essay. A single orchestrator makes every decision. Parallel sub-agents are used only for read-only extraction, one per lease or report, and each returns cited JSON.

| Phase | Work | How agentic |
|---|---|---|
| P0 Intake | Classify documents and list what is missing | Low (Jev) |
| P1 Extraction | Turn documents into typed facts, each with its page or cell citation | Medium (parallel sub-agents) |
| P2 Screening | Fast go/no-go, under 10 min and $5 | Low (ZEN buy-box) |
| P3 Underwriting | Set assumptions, then build the Python model and the Excel mirror | Low for the math, medium for the assumptions |
| P4 Due diligence | Review leases, title, survey, Phase I, PCA, zoning and estoppels. Hunt for anomalies. | **High** (open investigation within a tool budget) |
| P5 IC memo | Write the memo. Every number must trace back to a fact or a calculation. | Medium |
| P6 LOI | Price comes from the return hurdle. Terms come from the policy tables. | Low (template) |
| P7 Deal-file QA | Check the deal file for completeness and consistency | Low |

**Rules the harness must follow:**
- **State lives on disk, not in the context window.** Keep `deal.json` (facts with sources), `assumptions.json`, `dd_checklist.json` and `todo.md`. Phases re-run when new documents arrive.
- **Quarantine against prompt injection.** Models that read seller documents get no tools and may only output schema-checked JSON. The orchestrator never sees raw document text.
- **Context engineering** (from Manus and Anthropic):
  - Keep the prompt prefix stable so caching works.
  - Fetch documents only when needed, by path and page.
  - Reset context between phases, passing a handoff file.
  - Keep errors visible in context.
- **Verification gates.** Deterministic checks run first; the LLM judge runs last.
  1. Coverage and checksum ties: rent roll to GPR, T-12 sums, unit counts.
  2. Python and Excel parity.
  3. ZEN rules, plus allowed ranges for each assumption.
  4. **Fragility test.** If the decision flips anywhere inside any assumption's plausible range, escalate.
  5. **Provenance checker.** Every number in the memo or LOI must link to a fact or calculation ID.
  6. A verifier from a different model family checks against a rubric, with at most 2 revision loops.
- **Escalation is a deliverable, not a stop.** The agent still produces the full deal file, marked BLOCKED or CONDITIONAL, with the question it needs answered and the default assumption it used.
- **Hard limits live in code, not prompts:** budgets, LOI term bands, and no external side effects.

## 3. Which model for what

Assign **roles**, not hard-coded models. Pin dated snapshots, and re-run the evals whenever a model changes.

| Role | Used in | Pick | Why |
|---|---|---|---|
| **Lead / orchestrator** (planning, judgment, assumptions, memo, LOI reasoning) | P3–P6, P4 investigation | The top frontier reasoning model: **Claude Opus 5.5**, or the current GPT or Gemini flagship, whichever scores best on *your* evals | Judgment and long-horizon reliability matter most here |
| **Sidekick** (bulk extraction, normalization, lease abstraction) | P1, P4 document reading | A mid-tier model: **Claude Sonnet 5.5**, or the GPT or Gemini mid-tier equivalent | High volume, so cost matters. Accuracy is enforced by checksums. |
| **Vision pass** (scans, tables in PDFs) | P1 second pass | **The strongest vision model on your extraction evals.** Research found Gemini strongest on PDF tables, and Claude sometimes silently dropping whole tables. | Verify with row-count checks |
| **Verifier / judge** | Gates and evals | **A different model family from the lead** (for example, Claude as lead means GPT or Gemini as judge) | Avoids a model rating its own errors favourably |
| **Fast decisions** | P0 classification, routing, red-flag scores | **Jev**, with **Claude Haiku 4.5** as fallback | Fast and cheap, returns typed probabilities |
| **Math, rules, Excel** | Everywhere | **No LLM.** Use Python, ZEN and LibreOffice. | LLMs make arithmetic errors, as finance benchmarks show |
| **Optimizer reflection** (GEPA proposals) | Training loop only | The strongest available reasoning model | Runs offline, so quality matters more than cost |

Prompts that are specific to one model family live in **per-model overlays**. The shared core (skills, rules, tools) must pass evals on every supported model family.

## 4. Should you use autoresearch? Yes, adapted.

Karpathy's autoresearch loop: an agent edits one file, runs against a fixed budget, checks one metric, keeps the change if it is better and reverts it if not, and uses git as the log. Use that loop to train the brain, with four changes the adversarial review showed are necessary:

1. **Edit prompts and skills, not model code.** `agent/` is editable. `evals/` is frozen and hidden from the optimizer. Humans edit only `program.md`.
2. **Use GEPA as the change proposer.** It reflects on failure traces and keeps a Pareto set of candidates. In its paper it beat RL fine-tuning (GRPO) while using up to 35x fewer runs. Give it failure *categories*, not the rubric text.
3. **Optimize one phase at a time on frozen fixtures, not the full pipeline.** End-to-end nightly runs would cost tens of thousands of dollars a night. Instead, run end-to-end weekly as a "no regression" check.
4. **Keep a change only if it is statistically real.** That means:
   - paired runs repeated 3 or more times
   - a confirmation run on a held-out set
   - no regression in counter-metrics: false flags, escalation rate, memo length, cost

**Other self-improvement methods:**
- **ACE (evolving playbook):** yes. Live runs only *propose* bullets, into a queue. Bullets get promoted through the same keep/revert loop. Only deterministic failure signals create candidates. Deal-specific data must be scrubbed out.
- **Agent Workflow Memory (turning successful runs into skills):** yes, later. Only use runs that passed the held-out set and an expert spot-check.
- **Darwin Gödel Machine, ADAS, AI Scientist:** no. They are research-grade. The Darwin Gödel Machine was caught gaming its own checker.

## 5. Evals (the "loss function"). Build these before the agent.

| Set | What | Role |
|---|---|---|
| Synthetic deals | A generator that produces OMs, rent rolls, T-12s and leases with planted defects (about 30 types) plus clean controls. Calibrated to CMBS data and rendered by a different model family. | Training signal only |
| Real documents | Public broker OMs, the expert's anonymized rent rolls and T-12s, and purchased dead-deal data rooms (about 230 docs) | Extraction accuracy |
| CMBS backtest | EDGAR ABS-EE multifamily loans with 36-month outcomes | Screening and underwriting risk accuracy |
| Transaction backtest | REIT acquisition filings plus county deed and assessor records | Cap rate and value accuracy |
| **Reality Set** | About 40 real deals (the expert's past deals, purchased deals, and public deals), plus 1 more per week | **The gate that decides whether a change is kept** |
| Adversarial | Prompt injection, contradictory documents, missing documents | Must reach 100% on critical items |
| Shadow | The expert's live deals run in parallel | Evidence for switching autonomy on |

- **Judgment calls:** the expert labels each assumption as a P10/median/P90 range, and each decision as pursue, pass, or "either is defensible."
- **One expert with no contract reviewers:** measure the expert's own consistency by re-labelling 10% of cases blind after 4+ weeks, and use the public outcome backtests as an independent check.
- **Graders:** deterministic checks first, then binary rubric items judged by a panel from a different model family, calibrated on at least 150 expert labels per critical item.
- **North star metric:** Clean Autonomous Deal Rate. A deal counts if it was not escalated, had no critical errors, and its decision falls within the expert's defensible set.
- **Autonomy bar:** each phase must meet its bar on the sealed Reality Set for 2 consecutive releases and on at least 20 shadow deals.

## 6. Build order

| Stage | Weeks | Deliverable |
|---|---|---|
| 0 Foundations | 0–3 | Schemas, the finance library with tests, the Brain Release manifest (a version hash of all brain files and model IDs), the security/NDA data-flow setup |
| 1 Evals first | 2–10 | The generator, backtests, Reality Set v0, calibrated judges, and a baseline score for every phase |
| 2 MVP brain | 6–16 | P0–P3, the screening memo, the template LOI, the Excel mirror, ZEN tables. **Shadow mode starts.** |
| 3 Training loop | 12–22 | The per-phase autoresearch + GEPA loop, the ACE queue, per-model overlays, the P5 memo |
| 4 Diligence and autonomy | 18–30 | P4, P7, Temporal, Jev calibrated. Each phase unlocks autonomy as it passes its bar. |

**Expert's 10 h/week:**

| Hours | Task |
|---|---|
| 3 | Labels for the judges |
| 2 | Shadow-mode deal review |
| 1.5 | Reviewing traces to find failure types |
| 1.5 | One new Reality Set case |
| 1 | Reviewing accepted changes |
| 1 | Spot-checking escalations |

## Verification of this blueprint
- **Every user constraint maps to a section:**
  - model-agnostic: §1, §3
  - autonomy: §2, §5
  - Python + Excel: §1
  - Jev: §1, §3
  - autoresearch: §4
  - limited expert time: §5, §6
- **Main sources:**
  - Karpathy autoresearch (github.com/karpathy/autoresearch)
  - GEPA (arxiv 2507.19457)
  - ACE (arxiv 2510.04618)
  - Anthropic engineering posts on context engineering, long-running harnesses and multi-agent research
  - Cognition's "Don't build multi-agents"
  - The Manus context-engineering post
  - Finance Agent Benchmark (arxiv 2508.00828)
  - TypeSafe Jev docs
  - GoRules ZEN
