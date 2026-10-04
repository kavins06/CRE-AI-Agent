# SPEC: engineering specification

> The product is an autonomous CRE acquisition analyst, "the Devin of real estate". Devin is the capability inspiration and, separately, the coding agent that builds this repository.

This spec is binding. If a task file conflicts with it, the spec wins: record the conflict in `PROGRESS.md` and follow the spec. Library usage details are in [LIBRARY_NOTES.md](LIBRARY_NOTES.md).

## 1. Repository layout

```
AGENTS.md  METHOD.md  PROGRESS.md  program.md  feature_list.json  CODEOWNERS
pyproject.toml  uv.lock  Makefile  init.sh  .env.example
config/
  models.yaml          # model per role (Section 9)
  budget.yaml          # per-task and nightly cost/latency/turn caps
  gates.yaml           # tolerances per gate
  toggles.default.yaml # external-action toggles, all false
brain/                 # EDITABLE BY THE LEARNING LOOP (the "weights")
  skills/<name>/SKILL.md (+ scripts/)
  prompts/<role>.md
  playbook/global.md   # ACE bullets
src/cre_brain/
  config/      domain/      state/       finance/     excel/
  rules/       extraction/  decisions/   gates/       deliverables/
  runner/      sandbox/     connectors/  memory/      onboarding/
  control/     data/        release/     cli.py
learning/              # autoresearch runner, GEPA adapters, keep rule
evals/                 # PROTECTED after M2: generator, defects, suites, scorers, splits
  holdout/             # never committed; CI-only
scripts/               # check_protected.py, verify_features.py, ...
tests/                 # unit and integration tests
tests/protected/       # PROTECTED: gate and evaluator contract tests
docker/box/            # local user-computer image (Section 3)
templates/codex/       # config.toml with profiles analyst/extractor/verifier/classifier + MCP server `cre`
clients/ts/            # generated typed TypeScript API client for the owner's UI
```

**Python 3.12, uv, ruff, mypy (strict on `src/`), pytest + hypothesis.** One package: `cre_brain`. A single `cre` CLI entry point (Typer).

## 2. Core interfaces (Python Protocols in `src/cre_brain/**/base.py`)

```python
class Runner(Protocol):                      # runner/base.py
    async def run(self, task: Task, box: Box, policy: Policy) -> AsyncIterator[AgentEvent]: ...
    # Implementations: CodexRunner (v1, development + training), FakeRunner (replays recorded transcripts),
    #   ClaudeRunner / OpenAIAgentsRunner (pre-commercial, M6). All share the same tools, skills, policy and gates.

class SandboxProvider(Protocol):             # sandbox/base.py
    async def create(self, user_id: str, image: str) -> Box: ...
    async def resume(self, user_id: str) -> Box: ...
    async def exec(self, box: Box, cmd: list[str], timeout_s: int) -> ExecResult: ...
    async def put(self, box: Box, local: Path, remote: str) -> None: ...
    async def get(self, box: Box, remote: str, local: Path) -> None: ...
    async def snapshot(self, box: Box) -> str: ...
    async def destroy(self, box: Box) -> None: ...
    # Implementations: LocalDockerProvider (v1, dev/CI). The owner's infra implements the same Protocol.

class DecisionModel(Protocol):               # decisions/base.py
    async def choice(self, state: dict, question: str, options: dict[str, str]) -> ChoiceResult: ...
    async def score(self, state: dict, question: str, levels: list[str]) -> ScoreResult: ...
    async def yes_no(self, state: dict, question: str) -> float: ...
    # Implementations: JevDecisionModel (typesafe-sdk, optional), CodexDecisionModel (one-shot `codex exec` with output schema)

class MarketDataProvider(Protocol):          # connectors/market_data.py
    async def rent_comps(self, geo: Geo, unit_mix: UnitMix) -> list[Comp]: ...
    async def cap_rates(self, geo: Geo, asset: AssetClass) -> Series: ...
    async def macro(self, series_id: str) -> Series: ...
    # v1: PublicMarketData (FRED/ACS/HUD/BLS/Cook). Later: CoStar, Yardi Matrix, Trepp.

class EmailConnector, DataRoomConnector, DocumentStore, Notifier  # connectors/*.py
    # v1: OutboxEmail (writes drafts to outbox/), LocalDocumentStore, StubDataRoom, EventNotifier

class ExcelEngine(Protocol):                 # excel/base.py
    def recalc(self, path: Path) -> Path: ...
    # LibreOfficeEngine (v1), GraphExcelEngine (licensed, adapter + contract tests only)
```

All provider choices are made in config, never hard-coded.

## 3. The user computer (box image contract)

The owner's infrastructure must provide boxes that satisfy this contract. `docker/box/Dockerfile` is the reference image.

- Linux x86_64, at least 2 vCPU, 4 GB RAM, 20 GB persistent disk. Sleeps when idle and resumes with its disk intact.
- Installed:
  - Python 3.12 with `cre_brain` installed
  - the Codex CLI (Node.js), authenticated by the owner's setup; the Claude Agent SDK is added later
  - LibreOffice headless with the recalc macro installed
  - Chromium via Playwright
  - fonts for PDF rendering
- Filesystem under `/home/agent`:
  ```
  firms/<firm_id>/playbook/   # read-only sync from control plane
  memory/                     # this user's private memory
  deals/<deal_id>/{docs,work,model,deliverables,todo.md,progress.md}
  inbox/   outbox/   .agents/skills/  (synced from brain/skills + firm skills; the Agent Skills standard, which Codex reads)
  .codex/config.toml          # MCP server `cre`, profiles (analyst, extractor, verifier)
  ```
- Network: outbound access to the model APIs and the allowed data domains only. **Inbound: none, except from the control plane.**
- Secrets are injected as environment variables at session start. They are never written to disk.
- **The Codex CLI is installed and authenticated** by the owner's setup. It is the v1 analyst runtime (§10).
- **OS-level enforcement.** This is the primary layer; tool policy is the second layer:
  - the agent runs as a non-root `agent` user
  - `firms/` is read-only
  - only `deals/`, `outbox/`, `memory/` and the scratch dir are writable
  - all egress goes through an allowlisting proxy (model API, allowed data domains)
  - Codex runs with `--sandbox workspace-write`, with the workspace set to the deal folder
- A small **box agent** service runs in each box (§10.8).
- **Isolation tests** (T031):
  - with all tool policy disabled, a shell write outside the allowed paths fails, and so does a `curl` to a non-allowlisted domain
  - user A's box cannot read user B's files
  - a box has no route to other boxes
  - secrets are absent from snapshots

## 4. Domain model (`domain/`, Pydantic v2)

```python
class ClaimType(StrEnum): SELLER_ASSERTION, VERIFIED_FACT, INTERPRETATION, APPROVED_POLICY, CONFLICT, ASSUMPTION
class Provenance(BaseModel): doc_id: str; page: int | None; bbox: tuple[float,float,float,float] | None
                             sheet: str | None; cell: str | None; quote: str | None  # short span
class Fact(BaseModel):  fact_id; deal_id; key: str  # e.g. "rent_roll.unit[12].market_rent"
                         value: Decimal | str | date | bool; unit: str | None
                         claim_type: ClaimType; provenance: list[Provenance]
                         valid_time: DateRange | None; known_at: datetime; version: int
class Assumption(BaseModel): key; value; low; high; rationale; sources: list[str]
                         is_proxy: bool; as_of: date; set_by: Literal["agent","firm_policy","user"]
class CalcResult(BaseModel): calc_id; fn: str; inputs: dict[str,str]  # ids of facts/assumptions
                         outputs: dict[str, Decimal]; code_version: str
class Question(BaseModel): q_id; deal_id; text; why_it_matters; default_used: str
                         affects: list[str]; status: Literal["open","answered","withdrawn"]; answer: str | None
class Deliverable(BaseModel): d_id; deal_id; kind: DeliverableKind; status: Literal["draft","final","blocked","conditional","stale"]
                         path: str; gate_results: list[GateResult]; depends_on: list[str]
class Task(BaseModel): task_id; user_id; firm_id; deal_id; request: str; files: list[str]
                         requested: list[DeliverableKind] | None; created_at
```

```python
class AgentEvent(BaseModel):          # one schema for streaming, replay, audit, FakeRunner transcripts
    event_id: str          # ULID
    task_id: str; seq: int # per-task monotonic sequence
    ts: datetime
    source: Literal["agent","subagent","tool","gate","user","system"]
    kind: Literal["message","tool_call","tool_result","question","answer","user_message",
                  "gate_result","deliverable","compaction","budget","confirmation_request",
                  "confirmation_response","stuck","error","escalation","runner_raw"]
    cause_id: str | None   # the event this responds to (e.g. tool_result -> tool_call)
    release_id: str; runner: str; schema_version: int = 1
    payload: dict          # REDACTED before storage/streaming (§15)
```

`DeliverableKind`: `SCREEN`, `UW_MODEL`, `IC_MEMO`, `DD_TRACKER`, `LOI`, `BROKER_QUESTIONS`, `LEASE_ABSTRACT`, `DEAL_COMPARISON`, `ESCALATION`.

## 5. State store and invalidation (`state/`)
- SQLAlchemy 2 / SQLModel. SQLite for dev and tests, Postgres in production (same migrations, Alembic).
- Tables:
  - `facts`, `assumptions`, `calcs`, `questions`, `deliverables`
  - `edges(src_id, dst_id)`
  - `events`: append-only, used for UI streaming and session replay
- Facts are versioned, never updated in place. A new version is a new row, and `current` is a view.
- **Invalidation.** When a fact, assumption or answer changes, `graph.mark_stale(id)` marks every descendant `stale`, transitively. The agent's next step regenerates the stale items, highest dependency first.
  - Required test: change one unit's rent, then assert that the NOI calc, the UW model, the IC memo and the LOI all go stale, and that nothing unrelated does.

## 6. Finance library (`finance/`), deterministic and LLM-free
Modules:
- `rentroll.py`: unit-level normalization, occupancy, GPR, loss-to-lease, concessions
- `t12.py`: line mapping to a standard chart of accounts, annualization rules, missing-month policy
- `proforma.py`: annual/monthly cash flows, growth, vacancy, reserves, capex
- `debt.py`: sizing as `min(LTV, DSCR, debt yield)`; amortization; IO periods
- `returns.py`: IRR and XIRR via pyxirr, with **multi-root detection** (sign changes > 1 → compute all roots in a bracket and report `ambiguous`); equity multiple; cash-on-cash; NPV with the Excel convention (`start_from_zero=False`)
- `exit.py`
- `scenarios.py`: sensitivity grids, **joint downside scenarios** (correlated rent, vacancy and exit-cap shocks), fragility test, max-supportable-price solver

Rules:
- Every public function returns `CalcResult` with the input IDs, so outputs are traceable.
- Money is `Decimal`, with rounding only at presentation.
- Property tests:
  - sources = uses
  - amortization balance → 0 at maturity
  - IRR of `[-P, …]` reproduces NPV = 0
  - DSCR monotonic in loan size

## 7. Excel mirror (`excel/`)
- **Reference template:** `excel/templates/mf_standard.xlsx`, generated by code. It uses only the function whitelist in `gates.yaml`, has **no circular references** (circular items are solved in Python and written as labelled inputs), and has named ranges for every input and output.
- **Template map:** JSON mapping `calc_id/fact key ↔ sheet!cell`. Firm templates get their own map, built at onboarding (Section 14).
- **Build sequence:**
  1. Write the inputs with openpyxl.
  2. `ExcelEngine.recalc`.
  3. Read the recalculated values with `data_only=True`.
  4. **Parity diff** against Python: absolute tolerance $1, relative tolerance 1e-6, configurable.
  5. Error scan: `#REF!`, `#DIV/0!`, `#VALUE!`, `#NAME?`.
- Never save a workbook that was loaded with `data_only=True`.

## 8. Rules (`rules/`, zen-engine JDM)
Tables in `rules/tables/`:
- `buy_box.default.json`: placeholder mandate; each firm's comes from onboarding
- `assumption_ranges.mf.json`: by market tier, vintage and class
- `loi_policy.default.json`: price bands vs. max-supportable price, deposit, DD period, closing period
- `missing_data_policy.json`: impute + flag, or ask
- `escalation_policy.json`

The wrapper returns a typed result plus a trace.

## 9. Models and config
`config/models.yaml` maps each **role** to a runner and model. v1 uses the Codex CLI for all LLM roles:
```yaml
runner: codex                 # codex | fake | claude_sdk | openai_agents (later)
roles:
  lead:          {runner: codex, profile: analyst,   model: "<codex default>"}
  extraction:    {runner: codex, profile: extractor, model: "<codex default or faster>"}
  verifier:      {runner: codex, profile: verifier,  model: "<codex default>"}   # separate session, different prompt
  fast_decision: {provider: typesafe, model: jev-latest, fallback: {runner: codex, profile: classifier}}
  reflection:    {runner: codex, profile: analyst,   model: "<codex default>"}   # GEPA reflection
```
- Model names live **only** in config. The owner sets them.
- `config.live_enabled(role)` is true when the role's runner is usable: the Codex CLI is installed and authenticated (`codex login status` succeeds), or the SDK key is present for later runners. When it is false, callers skip live work cleanly and log `SKIPPED_NO_RUNNER`.
- CI never calls live models; it uses FakeRunner.
- **Later:** when the product commercializes, add the Claude Agent SDK and/or OpenAI Agents/Codex SDK runners. Re-run the full eval suite on each, and re-tune the per-runner prompt overlays (`brain/prompts/overlays/<runner>/`).

## 10. Runner and the agent loop (`runner/`)

### 10.1 CodexRunner (v1)
- Runs the **Codex CLI headless inside the user's box**:
  ```
  codex exec --json --profile analyst --cd /home/agent/deals/<deal_id> --sandbox workspace-write "<task prompt>"
  ```
  The JSONL events stream to the box agent, which normalizes them into `AgentEvent`s; the raw form is kept as `runner_raw`.
- Analyst instructions:
  - the deal folder's `AGENTS.md`, generated per task from `brain/prompts/lead.md`, the firm playbook summary, retrieved user memory and the deliverable catalog
  - Skills from `.agents/skills/`
- Tools: the `cre` MCP server (10.4), configured in `.codex/config.toml`. Codex's built-in shell and file tools work inside the sandbox.
- Plan recitation: the agent keeps `todo.md` and `progress.md` in the deal folder.
- Sessions:
  - a task can span several `codex exec` segments
  - `codex exec resume <session_id>` continues a segment
  - the session ID is persisted in the state DB
- [verify in T030]:
  - the exact flags, profile and config keys
  - the `--output-schema` support
  - the resume command
  - the non-interactive MCP tool-approval setting (openai/codex issue #24135); pin the working setting in `.codex/config.toml`

### 10.2 Quarantined extraction
- Each document or document group is extracted in a **separate one-shot `codex exec`** with these settings:
  - `--profile extractor`
  - `--sandbox read-only`
  - **no MCP servers**
  - network disabled
  - input is only the pre-parsed text and tables file plus page and cell anchors
  - `--output-schema` set to the JSON schema for that document type
- Pre-parse: XLSX/CSV is read natively as cells; PDFs go through Docling, with the Reducto adapter optional.
- Output → `Fact`s with `claim_type=SELLER_ASSERTION` and provenance → the checksum and coverage gates.
- The lead analyst session never reads raw seller text. It reads typed facts through `facts_get`.
- Extractions run in parallel up to `budget.yaml:max_parallel_extractions`.

### 10.3 Enforcement layers (runner-agnostic)
| Layer | Enforces |
|---|---|
| **OS / infra** (§3) | Writable paths, egress allowlist, non-root user, cross-user isolation |
| **Codex sandbox** | `workspace-write` for analyst sessions; `read-only` and no network for extraction, verifier and classifier sessions |
| **Tool server policy** (`runner/policy.py`, inside every `cre` tool) | External-action toggles (`off` / `ask` / `on`, default `off`); budgets (turns, sessions, wall-clock); `finalize_deliverable` runs the gates and refuses with the failure list; `send_external` refuses unless the toggle is `on`; with `ask` it emits a `confirmation_request` and waits |
| **Stuck detector** (`runner/stuck.py`, in the box agent) | Watches the event stream for repeated identical tool calls and results, repeated errors and no-progress loops. It nudges once (a message to the session), then stops the segment and emits `ESCALATION` |
| **SDK hooks** (later runners only) | A defence-in-depth mirror of the tool-server policy |

Gates live in the tool server, not in the runner. Any runner (Codex, Claude, OpenAI, Devin acting as the analyst) therefore gets the same enforcement.

### 10.4 CRE tools (`cre` MCP server **and** `cre tool …` CLI)
Every tool is available in two forms: as an MCP tool, and as an identical CLI command (`cre tool finance_run --json '{...}'`). The tools are:
- `facts_get` / `facts_put` / `assumption_set`
- `finance_run(fn, args)`
- `excel_build(template, deal)` → path
- `excel_recalc_parity(path)`
- `rules_eval(table, input)`
- `market_data(query)`
- `decide(kind, state, question)`
- `browse(url, goal)`: Playwright, toggle-gated, egress-allowlisted
- `ask_user(question, why, default, affects)`
- `finalize_deliverable(kind, path)`
- `draft_external(kind, to, body)` → `outbox/`
- `send_external(...)`: requires the toggle

Tools return concise JSON with actionable error messages.

### 10.5 Ask-and-continue protocol
1. `ask_user` creates a `Question`, emits an event, records `default_used` as an `Assumption(set_by="agent")`, and links the edges to the items it `affects`.
2. The agent continues.
3. On `POST /tasks/{id}/answers`, the control plane updates the assumption, calls `mark_stale`, and starts a resume segment with a short message listing the stale items.
4. The agent regenerates the stale items.

`POST /tasks/{id}/messages` (a mid-task user instruction) works the same way: it is delivered at the next segment boundary, or immediately via interrupt-and-resume.

### 10.6 Screen-first fast path and parallelism
- `SCREEN` runs before anything else when the request includes it or when the deal is new. Steps:
  1. classify the documents
  2. extract the OM headline numbers and the summary rent roll
  3. run the buy-box
  4. emit a screen deliverable
- **Target: under 5 minutes at p50.**
- **Parallelism:**
  - extraction sessions run concurrently, up to `max_parallel_extractions`
  - deliverables that don't depend on each other run as separate analyst segments, up to `max_parallel_sessions` (default 2)
  - the box minimum is 4 vCPU and 8 GB RAM when parallelism is above 1

### 10.7 FakeRunner
- Replays a recorded `AgentEvent` JSONL transcript against the real tools and gates.
- This is how CI tests orchestration without any live model.
- Record new transcripts with `cre record --task …` when a live runner is available.

### 10.8 Box agent contract (control plane ↔ box)
- `cre-boxd` is a small service in each box. It **connects outbound** to the control plane over an authenticated WebSocket; boxes accept no inbound traffic.
- Commands:
  - `start_or_attach(task_id, segment_no)`: **idempotent**; the same key never starts a second session
  - `interrupt(task_id)`, `pause`, `resume`
  - `deliver_message(task_id, text)`
  - `sync_playbook(firm_id)`
- Events stream outbound with `seq` and are acknowledged by the control plane. Unacknowledged events are re-sent after reconnect, and duplicates are dropped by `(task_id, seq)`.
- Heartbeat every 10 s. Missing 3 heartbeats marks the box `unreachable`. The task waits up to `budget.yaml:box_reconnect_s`, then re-attaches when the box returns.
- **Recovery when the box disk is lost:** create a fresh box, re-sync the firm playbook and memory, and rebuild the deal folder from the state DB (facts, assumptions, deliverables, `todo.md` snapshot). Then start a new segment with a recovery message. Events record the recovery.
- DBOS steps use step keys `(task_id, segment_no)` so re-execution is idempotent.

## 11. Gates (`gates/`), PROTECTED after M3; invoked by `finalize_deliverable` in the tool server
Each gate implements `check(deal_id, deliverable) -> GateResult(passed, failures: list[str], metrics)`. The catalog maps each `DeliverableKind` to its gate list:

| Kind | Gates |
|---|---|
| any extraction | coverage, checksums |
| SCREEN | coverage, buy_box, provenance |
| UW_MODEL | checksums, parity, excel_errors, assumption_ranges, irr_sanity, fragility |
| IC_MEMO | provenance_entailment, numbers_match_model, coverage_of_required_sections, verifier |
| LOI | policy_bands, provenance, verifier |
| DD_TRACKER | coverage (checklist items), provenance |
| BROKER_QUESTIONS, LEASE_ABSTRACT, DEAL_COMPARISON | provenance |

**Provenance + entailment:** every number in prose is extracted and must resolve to a fact or calc ID within tolerance. A verifier-model call checks that the cited source supports the claim.

## 12. Control plane (`control/`)
- **FastAPI, authenticated.** Every route requires a token carrying `user_id` and `firm_id` claims. Every query is scoped by them. An API isolation test proves that user A gets 404 on user B's tasks.
  - `POST /tasks` · `GET /tasks/{id}` · `GET /tasks/{id}/deliverables`
  - `POST /tasks/{id}/answers` · `POST /tasks/{id}/messages` (mid-task instruction)
  - `POST /tasks/{id}/interrupt` · `/pause` · `/resume`
  - `POST /tasks/{id}/confirmations/{cid}` (approve or deny an `ask`-toggled action)
  - `GET /tasks/{id}/events?after_seq=&limit=` (paged) and `GET /tasks/{id}/events/stream` (SSE, resumable with `Last-Event-ID`)
  - `POST /corrections` · `POST /firms/{id}/onboard` · `PUT /users/{id}/toggles`
- **OpenAPI.** The spec is published at `/openapi.json`. A generated typed TypeScript client goes in `clients/ts/` for the owner's UI team.
- **DBOS:**
  - `@DBOS.workflow()` per task; steps are box attach, runner segments, gate runs and deliverable publish, keyed as in §10.8
  - a crashed task resumes from its last completed step
- **Events** are stored in the `events` table after redaction, then streamed. A session can be replayed from events.
- **Budget meter** per task and per user. A hard stop emits a `BLOCKED` escalation deliverable.
- **Stress test (T041):**
  - N concurrent tasks
  - a slow SSE consumer
  - a killed control-plane worker
  - a dropped box connection

  Every case must stay within its latency and memory budgets.

## 13. Memory (`memory/`)
| Layer | Store | Access |
|---|---|---|
| Global | `brain/` (git) | All boxes, synced read-only |
| Firm | `firms/<id>/playbook/` | That firm's users |
| User | `memory/` in the box + a DB mirror | That user |

- **Retrieval:** at task start, the relevant playbook bullets and user corrections, chosen by tag and embedding similarity, are added to the lead prompt, within a token cap.
- **Sanitization gate (`memory/sanitize.py`):** runs before anything flows from user or firm to global. It removes:
  - names, addresses, tenant and sponsor entities (NER + deal-entity dictionary)
  - exact dollar amounts and unit counts (bucketed)
  - document quotes

  Any residual match against that firm's entity dictionary fails the gate. Tests plant leaks and assert that they are caught.

## 14. Firm onboarding (`onboarding/`)
1. **Template mapping.** The firm uploads its Excel model. The agent proposes a cell map, then a synthetic deal is run through both the reference and the firm template. Parity must pass before the map is saved.
2. **Buy-box and policy.** The firm's criteria, in text or a form, are converted into JDM tables. Rule tests are generated from examples the firm confirms.
3. **Memo style.** From sample memos, build a section outline, tone and formatting guide → `firms/<id>/playbook/memo_style.md`.

## 15. Security and data handling
- Seller documents are untrusted; quarantine is enforced (10.2).
- Secrets come only from the environment.
- **Redaction.** Secrets and credentials are masked in events, traces and exports before they are stored or streamed. Tenant identifiers are excluded from any global or learning artifact. Planted-secret tests cover this.
- Per-tenant encryption keys are an infrastructure concern documented in HUMAN_SETUP.
- No firm's data appears in global artifacts. This is enforced by the sanitization gate plus a CI test.
- Never use LiteLLM, HyperFormula (unless licensed), Marker, ii-agent's bundled office skills, or OpenHands code as a dependency. OpenHands patterns are borrowed and re-implemented (MIT, attribution in comments).

## 16. Observability
- OpenTelemetry spans for each tool call, model call and gate, exported to Langfuse (self-hosted) when configured.
- Per-task metrics: cost, latency per deliverable, question count, gate failures, revisions.
