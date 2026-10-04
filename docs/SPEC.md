# SPEC: engineering specification

> The product is an autonomous CRE acquisition analyst, "the Devin of real estate". Devin is the capability inspiration and, separately, the coding agent that builds this repository.

This spec is binding. If a task file conflicts with it, the spec wins: record the conflict in `PROGRESS.md` and follow the spec. Library details are in [LIBRARY_NOTES.md](LIBRARY_NOTES.md). Items marked **[verify]** must be confirmed on the installed version by the task that first uses them.

## 1. Repository layout

```
AGENTS.md  METHOD.md  PROGRESS.md  program.md  feature_list.json  CODEOWNERS
pyproject.toml  uv.lock  Makefile  init.sh  .env.example  docker-compose.yml
config/
  models.yaml          # runner + model per role (Section 9)
  budget.yaml          # per-task and nightly caps (sessions, wall-clock, tokens, parallelism)
  gates.yaml           # tolerances per gate, Excel function whitelist
  toggles.default.yaml # external actions: off | ask | on (default off)
brain/                 # EDITABLE BY THE LEARNING LOOP (the "weights")
  skills/<name>/SKILL.md (+ scripts/)
  prompts/<role>.md   prompts/overlays/<runner>/
  playbook/global.md   # ACE bullets
src/cre_brain/
  config/  domain/  state/  finance/  excel/  rules/  extraction/  decisions/
  gates/  deliverables/  runner/  sandbox/  connectors/  memory/  onboarding/
  control/  data/  release/  cli.py
learning/              # autoresearch runner, GEPA proposer, keep rule (keep_rule.py protected)
evals/                 # PUBLIC eval framework: generator, defects, scorers, suites (protected)
reports/               # eval and baseline reports (NOT protected; written by make eval)
templates/codex/       # Codex config + profiles, AGENTS.md templates for analyst sessions
docker/box/            # reference user-computer image
docker/extract/        # throwaway extraction container image
clients/ts/            # generated TypeScript API client (M6)
scripts/               # guard scripts (owner-authored ones are protected)
tests/  tests/protected/  tests/fixtures/
```

**The private eval repo is separate.** It is `<owner>/cre-ai-agent-evals-private`, which Devin cannot access. It holds the selection-holdout and sealed-test case seeds and configs, the real-anchor gold answers, and owner labels. Only CI (via `EVALS_PRIVATE_TOKEN`) and the owner's scoring job read it. See EVALS §1.

**Tooling:** Python 3.12, uv, ruff, mypy (strict on `src/`), pytest + hypothesis. One package, `cre_brain`, with a single `cre` CLI (Typer).

## 2. Core interfaces (Protocols in `src/cre_brain/**/base.py`)

```python
class Runner(Protocol):                      # runner/base.py
    async def run_segment(self, seg: SegmentSpec, ws: Workspace, policy: Policy) -> AsyncIterator[AgentEvent]: ...
    # v1: CodexRunner (Codex CLI), FakeRunner (replays `cre record` transcripts: plumbing only).
    # M8: ClaudeRunner (claude-agent-sdk), OpenAIAgentsRunner. Same tools, policy, gates.

class SandboxProvider(Protocol):             # sandbox/base.py
    async def create(self, user_id: str, image: str) -> Box: ...
    async def resume(self, user_id: str) -> Box: ...
    async def exec(self, box: Box, cmd: list[str], timeout_s: int) -> ExecResult: ...
    async def put(self, box: Box, local: Path, remote: str) -> None: ...
    async def get(self, box: Box, remote: str, local: Path) -> None: ...
    async def snapshot(self, box: Box) -> str: ...
    async def destroy(self, box: Box) -> None: ...
    # v1: LocalDockerProvider. The owner's infrastructure implements the same Protocol + passes tests/sandbox/contract.py.

class DecisionModel(Protocol):               # decisions/base.py
    async def choice(self, state: dict, question: str, options: dict[str, str]) -> ChoiceResult: ...
    async def score(self, state: dict, question: str, levels: list[str]) -> ScoreResult: ...
    async def yes_no(self, state: dict, question: str) -> float: ...
    # v1: RuleDecisionModel (deterministic heuristics) + CodexDecisionModel. M8: JevDecisionModel.

class MarketDataProvider(Protocol):          # connectors/market_data.py
    async def rent_comps(self, geo: Geo, unit_mix: UnitMix) -> list[Comp]: ...
    async def expense_benchmarks(self, geo: Geo, vintage: int, units: int) -> ExpenseBench: ...
    async def cap_rates(self, geo: Geo, asset: AssetClass) -> Series: ...
    async def macro(self, series_id: str) -> Series: ...
    # v1: PublicMarketData (FRED/ACS/HUD/BLS/Cook). It returns NO property-level rent comps; see §6.6.
    # Later: CoStar, Yardi Matrix, Trepp (licensed).

class EmailConnector, DataRoomConnector, DocumentStore, Notifier   # connectors/*.py, v1 stubs/outbox

class ExcelEngine(Protocol):                 # excel/base.py
    def recalc(self, path: Path) -> Path: ...
    # v1: LibreOfficeEngine (Python UNO / unoserver). Licensed: GraphExcelEngine (real Excel).
```

All provider choices are made in config, never hard-coded.

## 3. The user computer (box image contract)

The owner's infrastructure provides boxes that satisfy this contract. `docker/box/Dockerfile` is the reference image.

- **Hardware:** Linux x86_64. Minimum 2 vCPU / 4 GB with `max_parallel_sessions=1`. Use 4 vCPU / 8 GB at the default `max_parallel_sessions=2`. 20 GB persistent disk. The box sleeps when idle and resumes with its disk intact.
- **Installed:**
  - Python 3.12 with `cre_brain`
  - Codex CLI (Node.js)
  - LibreOffice headless + unoserver
  - Chromium via Playwright
  - fonts
  - container runtime access for launching extraction containers (rootless Docker/Podman, or a sidecar API the owner provides)
- **Filesystem.** The analyst session's mount is **only** `/home/agent/work`:
  ```
  /home/agent/work/
    firms/<firm_id>/playbook/        # read-only bind
    memory/                          # user-private
    deals/<deal_id>/{facts.json,todo.md,progress.md,model/,deliverables/,scratch/}
    outbox/   .agents/skills/  (synced from brain + firm)   .codex/config.toml
  /srv/raw/<deal_id>/                # RAW SELLER DOCUMENTS - NOT mounted into analyst sessions
  /home/agent/inbox/                 # drop folder, watched by cre-boxd
  ```
- **Raw seller documents never enter the analyst session's filesystem.** Only the extraction pipeline (§10.2) reads `/srv/raw`.
- **OS-level enforcement** (primary layer):
  - non-root `agent` user
  - `firms/` read-only
  - writable only `deals/`, `outbox/`, `memory/`, `scratch/`
  - all egress through the owner's allowlisting proxy (model API + allowed data domains)
  - no box-to-box network
- **Codex sandbox inside the box.** Codex's bubblewrap sandbox may not work inside containers [verify in T030]. If it fails, the **container is the sandbox**: run Codex with `danger-full-access` *inside* the restricted container, and the OS rules above apply. Never use that mode on a host.
- **Secrets** are injected as environment variables per session and never written to the workspace. Codex auth: see §9.
- **Isolation tests (T031), run with all tool policy disabled:**
  - a shell write outside the allowed paths fails
  - `curl` to a non-allowlisted domain fails
  - reading `/srv/raw` from an analyst session fails
  - user A cannot read user B
  - no box-to-box network
  - secrets are absent from snapshots

## 4. Domain model (`domain/`, Pydantic v2)

```python
class ClaimType(StrEnum): SELLER_ASSERTION, VERIFIED_FACT, INTERPRETATION, APPROVED_POLICY, CONFLICT, ASSUMPTION
class Provenance(BaseModel): doc_id; page: int|None; bbox: tuple[float,float,float,float]|None
                             sheet: str|None; cell: str|None; quote: str|None   # short span
class Fact(BaseModel):  fact_id; deal_id; key: str; value: Decimal|str|date|bool; unit: str|None
                        claim_type: ClaimType; provenance: list[Provenance]
                        valid_time: DateRange|None; known_at: datetime; version: int
class Assumption(BaseModel): key; value; low; high; rationale; sources: list[str]; is_proxy: bool
                        as_of: date; set_by: Literal["agent","firm_policy","user"]
class CalcResult(BaseModel): calc_id; fn: str; inputs: dict[str,str]; outputs: dict[str, Decimal]; code_version: str
class Question(BaseModel): q_id; task_id; deal_id; text; why_it_matters; default_used: str
                        affects: list[str]; status: Literal["open","answered","withdrawn"]; answer: str|None
class Deliverable(BaseModel): d_id; deal_ids: list[str]; kind: DeliverableKind; version: int
                        status: Literal["draft","final","blocked","conditional","stale","superseded"]
                        path: str; gate_results: list[GateResult]; depends_on: list[str]
                        edited_by_user: bool = False; parent_version: int|None
class Task(BaseModel): task_id; user_id; firm_id; deal_ids: list[str]   # multi-deal tasks (comparisons, portfolios)
                        request: str; requested: list[DeliverableKind]|None; created_at
class AgentEvent(BaseModel):          # ONE schema for streaming, replay, audit and transcripts
    event_id: str                      # ULID
    task_id: str
    seq: int | None                    # assigned by the CONTROL PLANE on ingest; monotonic per task
    origin: tuple[str, int, int] | None  # (box_id, segment_no, local_seq), set by the box; used for acks/dedupe
    ts: datetime
    source: Literal["agent","extractor","tool","gate","user","system"]
    kind: Literal["message","tool_call","tool_result","question","answer","user_message",
                  "gate_result","deliverable","stale","compaction","budget","usage",
                  "confirmation_request","confirmation_response","interrupt","pause","resume",
                  "segment_start","segment_end","recovery","stuck","error","escalation","runner_raw"]
    cause_id: str | None; release_id: str; runner: str; schema_version: int = 1
    payload: dict                      # REDACTED before storage/streaming (§15)
```

**`DeliverableKind` values:**
`SCREEN`, `UW_MODEL`, `IC_MEMO`, `DD_TRACKER`, `LOI`, `BROKER_QUESTIONS`, `LEASE_ABSTRACT`, `DEAL_COMPARISON`, `RENT_COMP_ANALYSIS`, `DEBT_QUOTE_SUMMARY`, `ESCALATION`.

**Deliverable versioning.** Every regeneration creates a new version; the old one becomes `superseded`. A user-edited deliverable (for example an Excel model re-uploaded with changes) is ingested as a new version with `edited_by_user=True`. Its diff against the parent produces `Correction` records (LEARNING §6).

## 5. State store and invalidation (`state/`)
- SQLAlchemy 2 + Alembic. **Postgres** for the control plane and integration tests (`docker compose up db`). SQLite only for unit tests.
- **Tables:**
  - `facts`, `assumptions`, `calcs`, `questions`, `deliverables` (versioned)
  - `edges(src_id, dst_id)`
  - `events` (append-only, `seq` assigned on insert)
  - `jobs` (§12)
  - `corrections`
- Facts and deliverables are **append-only versions**. The current state is a query.
- **Invalidation.** `graph.mark_stale(id)` marks every descendant stale, transitively, and emits `stale` events. `graph.stale_items(task)` returns them in topological order. Required test: changing one unit's rent marks the NOI calc, the UW model, the IC memo and the LOI stale, and nothing unrelated.

## 6. Finance library (`finance/`), deterministic and LLM-free
Every public function returns `CalcResult` with input IDs. Money is `Decimal`.

| Module | Contents |
|---|---|
| `rentroll.py` | Unit normalization; physical and economic occupancy; GPR; loss-to-lease; concessions; unit mix |
| `t12.py` | Chart-of-accounts mapping; annualization rules; missing-month policy; one-time item flags |
| `proforma.py` | Monthly/annual cash flows; growth; vacancy; credit loss; reserves |
| `taxes.py` | **Property-tax reassessment on sale** (jurisdiction rule table: reassess to price × ratio × millage, phase-ins, caps) |
| `valueadd.py` | **Renovation and unit-turn schedule**: units/month, downtime, cost per unit, rent premium, ramp |
| `debt.py` | Sizing as min(LTV, DSCR, debt yield); amortization; IO; **debt-quote comparison** (multiple term sheets); refinance |
| `returns.py` | IRR/XIRR via pyxirr. **Multi-IRR handling:** find all roots of NPV(r)=0 in (-0.99, 10) by bracketing; 0 roots → `undefined`, >1 → `ambiguous` with the roots listed, plus MIRR as the reported fallback. Equity multiple, cash-on-cash, Excel-convention NPV (`start_from_zero=False`) |
| `waterfall.py` | **JV waterfall**: preferred return, IRR hurdles, catch-up, promote tiers (dated cash flows) |
| `exit.py`, `holdsell.py` | Exit value; **hold vs. sell and refi scenarios** |
| `scenarios.py` | Sensitivity grids; **joint downside** (correlated shocks); fragility (§11); max-supportable-price solver |

**Property tests:**
- sources = uses
- the amortization balance reaches 0
- NPV at each reported IRR ≈ 0
- DSCR decreases as the loan grows
- waterfall tiers sum to total distributions
- the reassessed tax is ≥ the current tax when the price exceeds the assessed value (for full-reassessment jurisdictions)

### 6.6 Comps (honest scope)
- Public data has **no property-level rent comps**. In v1, `RENT_COMP_ANALYSIS` uses whatever the agent can source:
  - submarket rent proxies (ACS/HUD) and comps in the deal package, as seller assertions
  - `browse` results when the toggle allows it

  It labels all of these as proxies.
- Selection and adjustment logic (distance, vintage, class, unit-type normalization, amenity adjustments) is implemented and tested on synthetic comp sets, so licensed comps (CoStar, Yardi Matrix) plug in later.

## 7. Excel mirror (`excel/`)
- **Reference template** `templates/mf_standard.xlsx`:
  - generated by code
  - uses the function whitelist from `gates.yaml`
  - no circular references (circular items are solved in Python and written as labelled inputs)
  - named ranges for every input and output
- **Template map:** JSON mapping `calc_id/fact key ↔ sheet!cell`.
- **Build sequence:**
  1. openpyxl writes the inputs.
  2. `LibreOfficeEngine.recalc` (Python UNO via unoserver; one profile per worker) recalculates and **saves as .xlsx, keeping formulas and cached values**.
  3. That recalculated file **is the deliverable**.
  4. Read it with `data_only=True`.
  5. **Parity diff** against Python (absolute $1, relative 1e-6, configurable).
  6. Error scan: `#REF!`, `#DIV/0!`, `#VALUE!`, `#NAME?`.
- **Unsupported firm-template features** are detected at onboarding (§14), and the template is marked `needs_excel_engine`, used with a documented subset, or rejected with an explanation. These features are: circular references or iterative calc, data tables, macros (.xlsm), external links, and LibreOffice-incompatible functions.

## 8. Rules (`rules/`, zen-engine JDM)
Tables:
- `buy_box.default`
- `assumption_ranges.mf` (by market tier, vintage, class)
- `loi_policy.default`
- `missing_data_policy`
- `escalation_policy`
- `rent_regulation` (jurisdictions with rent control or stabilization → flag + required checks)
- `tax_reassessment` (jurisdiction rules)

The wrapper returns a typed result plus a trace.

## 9. Runners, models and auth
`config/models.yaml`:
```yaml
runner: codex                 # codex | fake | claude_sdk | openai_agents (M8)
roles:
  lead:       {runner: codex, profile: analyst,    model: "<owner sets>"}
  extraction: {runner: codex, profile: extractor,  model: "<owner sets>"}
  verifier:   {runner: codex, profile: verifier,   model: "<owner sets>"}   # separate session + independent prompt
  classifier: {runner: codex, profile: classifier, model: "<owner sets>"}
  reflection: {runner: codex, profile: reflector,  model: "<owner sets>"}   # GEPA proposer LM
```
- Model names live **only** in config.
- `config.live_enabled(role)` is true when the runner is usable: `codex login status` succeeds [verify the command and exit code], or the SDK key is present (M8). When false, live work is skipped through the approved markers.
- **Codex auth policy:**
  - **Development on public and synthetic data:** the owner's existing Codex CLI login is acceptable. A shared ChatGPT-login `auth.json` must be used by **one serialized job stream at a time**; set `budget.yaml:codex_login_max_concurrency` to 1.
  - **Any customer data, any parallel or multi-box use, production:** use **API-key auth** (`CODEX_API_KEY`) per box and per learning worker. HUMAN_SETUP records the owner's data-processing position.

## 10. Runner and the agent loop (`runner/`)

### 10.1 CodexRunner (v1)
- **Each analyst segment:**
  ```
  codex exec --json --cd /home/agent/work/deals/<deal_id> -p analyst [--sandbox <mode>] "<segment prompt>"
  ```
  Then:
  - JSONL from stdout → normalized `AgentEvent`s (raw kept as `runner_raw`)
  - `turn.completed` usage → `usage` events for the budget meter
- **Instructions:**
  - the deal folder's `AGENTS.md`, generated per segment from `brain/prompts/lead.md` + `brain/prompts/overlays/codex/` + firm playbook summary + user memory + the deliverable catalog
  - skills in `.agents/skills/` [verify the pickup path]
- **Tools:**
  - the `cre` MCP server (§10.4), configured in `.codex/config.toml` (`[mcp_servers.cre]`)
  - non-interactive approval via `default_tools_approval_mode` (or the narrowest working setting) [verify in T030; see openai/codex#24135]
- **Segments:**
  - a task runs as several **short segments**, each ≤ `budget.yaml:segment_max_min` (default 20) with its own turn and token caps
  - continue with `codex exec resume <session_id>` [verify]
  - session IDs are persisted
  - segments end on: deliverable finalized, `ask_user` with a material question, a pending confirmation, budget reached, interrupt, or stuck

### 10.2 Quarantined extraction (container-isolated, shell-only)
- Seller documents in `/srv/raw/<deal>` are first **pre-parsed by deterministic code**: openpyxl/pandas for XLSX/CSV, Docling for PDF, Reducto optional (licensed). Output is `parsed/<doc>.json` (text, tables, page and cell anchors).
- Each document is extracted in a **throwaway container** (`docker/extract`) with:
  - only that one parsed file mounted read-only
  - `--network none` (except an allowlisted model-API egress)
  - **no MCP servers**: a separate `CODEX_HOME` with an empty config, or `-c mcp_servers.cre.enabled=false` [verify]
  - `codex exec -p extractor --output-schema <doc_type>.schema.json`

  Codex still has a shell inside that container. The isolation comes from the container, not from "no tools".
- The schema-validated output is converted to `Fact`s (`SELLER_ASSERTION`) with provenance. Then the coverage and checksum gates run.
- **The lead analyst reads only typed facts** (through `facts_get` / `facts.json`), never raw seller text.

### 10.3 Enforcement layers (runner-agnostic)
| Layer | Enforces |
|---|---|
| **OS / container** (§3, §10.2) | Writable paths; no raw docs in analyst mounts; egress allowlist; non-root user; tenant isolation |
| **Tool server policy** (`runner/policy.py`, protected) | Toggles `off`/`ask`/`on` (default `off`); `finalize_deliverable` runs the gates and refuses with the failure list; `send_external` refuses unless allowed; wall-clock and session budgets |
| **Number provenance** (gates) | Every number in a deliverable must resolve to a stored `CalcResult` or `Fact`. Shell arithmetic by the model cannot pass. |
| **Budget meter** (box agent) | Token usage from `turn.completed` events; turns; segment wall-clock |
| **Stuck detector** (`runner/stuck.py`) | Repeated identical tool call and result, repeated errors, no-progress turns → one nudge → stop segment → `ESCALATION` |
| SDK hooks (M8 runners only) | Defence-in-depth mirror of the policy |

**`ask` toggles never block inside a tool call** (MCP calls time out; the Codex default is about 300 s [verify]):
1. The tool returns `{"status":"pending_confirmation","cid":...}` and emits a `confirmation_request`.
2. The agent records the item in `todo.md` and continues with other work, or ends the segment.
3. `POST /tasks/{id}/confirmations/{cid}` resumes it in a new segment.

### 10.4 CRE tools (`cre` MCP server **and** `cre tool <name>` CLI, one implementation)
- `facts_get` / `facts_put` / `assumption_set`
- `finance_run(fn, args)`
- `excel_build(template, deal)` → path
- `excel_recalc_parity(path)`
- `rules_eval(table, input)`
- `market_data(query)`
- `decide(kind, state, question)`
- `browse(url, goal)`: Playwright, toggle-gated, egress-allowlisted; page text is returned as **untrusted** content and stored as a seller-assertion-like `Fact` with provenance
- `ask_user(question, why, default, affects)`
- `finalize_deliverable(kind, path)`
- `draft_external(kind, to, body)` → `outbox/`
- `send_external(...)`
- `ingest_user_edit(deliverable_id, path)`

Tools return concise JSON with actionable errors.

Licensed public references use the single `cre_brain.knowledge` catalog and typed
`KnowledgeProvider.search(SearchRequest) -> SearchResult` seam (`docs/KNOWLEDGE.md`).
The future registry's `knowledge_search` must delegate to this same provider as
`cre knowledge search`, returning cited `global_public` reference chunks or
metadata-only references, never verified deal `Fact`/`CalcResult` evidence.
Imports remain operator-only/default-off until wired through this canonical
policy; reference-only/unknown/noncommercial rights prohibit ingestion. SEC is
disabled. Firm/user memory and evaluation truth must remain physically separate.

### 10.5 Ask-and-continue and mid-task messages
1. `ask_user` creates a `Question`, records `default_used` as an `Assumption(set_by="agent")`, adds edges to the `affects` items, and continues.
2. `POST /tasks/{id}/answers` updates the assumption, calls `mark_stale`, and queues a resume segment listing the stale items.
3. `POST /tasks/{id}/messages` queues a user instruction for the next segment. `/interrupt` stops the current segment immediately and starts a new one with the message.

### 10.6 Screen-first fast path and parallelism
- `SCREEN` steps:
  1. classify the documents (`RuleDecisionModel` first, then `CodexDecisionModel` when unsure)
  2. extract the headline numbers (OM summary, rent roll totals)
  3. run the buy-box
  4. emit the screen
- **Target: p50 ≤ 10 min in v1** on Codex. The target is tightened as runners get faster, and measured by evals.
- Parallelism:
  - extraction containers up to `max_parallel_extractions` (default 4)
  - independent deliverables as separate analyst segments up to `max_parallel_sessions` (default 2; this needs the 4 vCPU / 8 GB box)

### 10.7 Transcripts and FakeRunner
- `cre record` runs a live segment and stores `transcripts/<id>.jsonl` plus `manifest.json`:
  - Codex CLI version
  - SHA-256 of the raw Codex JSONL
  - SHA-256 of the normalized events
  - release ID
- **Never hand-edit a transcript.**
- **FakeRunner** replays a transcript's tool calls against the real tools, with **loose matching**: same tool, same argument keys; it ignores IDs. It asserts the **final state** (deliverables exist, gates pass). It proves plumbing only, **never quality**.
- When tool output changes legitimately, re-record with `cre record --refresh` in a dedicated task and note it in PROGRESS.md.

### 10.8 Box agent contract (`cre-boxd`, M6)
- **Connection:** outbound authenticated WebSocket to the control plane. No inbound ports.
- **Commands:**
  - `start_or_attach(task_id, segment_no)`: **idempotent on the box side**; if that segment is running or finished, it attaches or returns the result; it never starts a duplicate
  - `interrupt`, `pause`, `resume`
  - `deliver_message`
  - `sync_playbook`
- **Events** carry `origin=(box_id, segment_no, local_seq)`. The control plane acks by origin, assigns `seq` on insert, and de-duplicates by `origin`. Un-acked events are re-sent after reconnect.
- **Heartbeat** every 10 s. Three misses mark the box unreachable. The task waits up to `box_reconnect_s`, then re-attaches.
- **Recovery when the box disk is lost:**
  1. create a fresh box
  2. re-sync the playbook and memory
  3. rebuild `deals/<id>` from the state DB (facts, assumptions, deliverables, `todo.md` snapshot)
  4. start a new segment with a recovery message
  5. emit a `recovery` event

## 11. Gates (`gates/`, protected; invoked by `finalize_deliverable`)
Each gate has the signature `check(deliverable) -> GateResult(passed, failures, metrics)`.

| Kind | Gates |
|---|---|
| any extraction | coverage, checksums |
| SCREEN | coverage, buy_box, number_provenance |
| UW_MODEL | checksums, parity, excel_errors, assumption_ranges, irr_sanity, fragility, number_provenance |
| IC_MEMO | number_provenance, numbers_match_model, required_sections, entailment* |
| LOI | policy_bands, number_provenance, entailment* |
| DD_TRACKER | coverage (checklist), number_provenance |
| RENT_COMP_ANALYSIS, DEBT_QUOTE_SUMMARY, BROKER_QUESTIONS, LEASE_ABSTRACT, DEAL_COMPARISON | number_provenance |

- **Deterministic gates are the only blocking gates in v1.** Gates marked * (entailment and verifier, which are LLM-based) are **advisory**: they record a result but do not block. They become blocking only after the judge has been calibrated on owner labels (EVALS §3).
- **Fragility** is defined by margin, not by any flip. The recommendation is `CONDITIONAL` only if the go/no-go flips under a joint downside scenario whose assumptions all stay inside their P10–P90 ranges **and** the flip margin is below `gates.yaml:fragility_margin`. Otherwise the result is reported as a sensitivity, not a condition.
- **`number_provenance`** extracts every number from prose and tables and requires a match to a `CalcResult` or `Fact` within tolerance. Unmatched numbers fail.

## 12. Control plane (`control/`, M6; `cre run` CLI first in M2)
- **v1 first slice (M2):** `cre run --deal <path> --request "..."` runs the full loop locally with no API. A simple **Postgres `jobs` table**, with idempotent segments keyed by `(task_id, segment_no)` and a unique constraint, provides crash-resume. A worker crash re-attaches through `start_or_attach`; it never starts a duplicate. DBOS is not required in v1.
- **M6 API (FastAPI, authenticated).** Every route requires a token with `user_id` and `firm_id` claims, and every query is scoped by them. A **parameterized isolation test covers every route.**
  - `POST /tasks` · `GET /tasks/{id}` · `GET /tasks/{id}/deliverables[?version=]`
  - `POST /tasks/{id}/answers` · `POST /tasks/{id}/messages`
  - `POST /tasks/{id}/interrupt` · `/pause` · `/resume`
  - `POST /tasks/{id}/confirmations/{cid}`
  - `GET /tasks/{id}/events?after_seq=&limit=` · `GET /tasks/{id}/events/stream` (SSE, `Last-Event-ID`)
  - `POST /deliverables/{id}/edits` (upload a user-edited version) · `POST /corrections`
  - `POST /firms/{id}/onboard` · `PUT /users/{id}/toggles`
- **OpenAPI** is published, and a typed TS client is generated in `clients/ts/`.
- **Stress test:** N concurrent tasks, a slow SSE consumer, a killed worker, a dropped box connection. Everything must stay within the latency and memory budgets.

## 13. Memory (`memory/`)
| Layer | Store | Access |
|---|---|---|
| Global | `brain/` (git) | All boxes, read-only sync |
| Firm | `firms/<id>/playbook/` | That firm |
| User | `memory/` + DB mirror | That user |

- **Retrieval:** tag and embedding match, inserted into the segment's `AGENTS.md` within a token cap.
- **Sanitization gate** (`memory/sanitize.py`, protected; M7): NER + deal-entity dictionary + number bucketing + quote removal. It fails closed. Contract tests use ≥50 planted leaks. Until M7, **nothing is promoted to global from user or firm data.**

## 14. Firm onboarding (`onboarding/`, M7)
1. **Template mapping:**
   - a feature scan first (§7 unsupported features)
   - then a proposed cell map
   - a parity check on a synthetic deal through both templates
   - the map is saved only if parity passes
2. **Buy-box and policy** → JDM tables, with rule tests generated from examples the firm confirms.
3. **Memo style** → `firms/<id>/playbook/memo_style.md`.

## 15. Security and data handling
- **Seller documents and web pages are untrusted.** Quarantine and mount rules (§3, §10.2) apply.
- **Redaction:**
  - secrets, credentials and tokens are masked in events, traces and exports before storage or streaming (registered-secret list + pattern detectors)
  - planted-secret tests must catch 100%
- **No customer data** goes to the global brain except through the sanitization gate (M7+).
- **Codex auth** follows §9. Customer data never runs on a shared personal login.
- **Banned dependencies:** LiteLLM, DSPy, HyperFormula (unless licensed), Marker, ii-agent office skills, OpenHands packages. OpenHands *patterns* are re-implemented under MIT attribution.

## 16. Observability
- OpenTelemetry spans for each tool call, segment and gate, exported to Langfuse when configured.
- **Per-task metrics:** tokens, segments, latency per deliverable, question count, gate failures, revisions, stuck events.
