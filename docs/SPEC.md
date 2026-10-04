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
```

**Python 3.12, uv, ruff, mypy (strict on `src/`), pytest + hypothesis.** One package: `cre_brain`. A single `cre` CLI entry point (Typer).

## 2. Core interfaces (Python Protocols in `src/cre_brain/**/base.py`)

```python
class Runner(Protocol):                      # runner/base.py
    async def run(self, task: Task, box: Box, policy: Policy) -> AsyncIterator[AgentEvent]: ...
    # Implementations: ClaudeRunner (v1), FakeRunner (replays recorded transcripts), OpenAIRunner (M6)

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
    # Implementations: JevDecisionModel (typesafe-sdk), LLMDecisionModel (Haiku fallback)

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
  - the Claude Agent SDK and its CLI dependency (Node.js; see LIBRARY_NOTES)
  - LibreOffice headless with the recalc macro installed
  - Chromium via Playwright
  - fonts for PDF rendering
- Filesystem under `/home/agent`:
  ```
  firms/<firm_id>/playbook/   # read-only sync from control plane
  memory/                     # this user's private memory
  deals/<deal_id>/{docs,work,model,deliverables,todo.md,progress.md}
  inbox/   outbox/   .claude/skills/  (synced from brain/skills + firm skills)
  ```
- Network: outbound access to the model APIs and the allowed data domains only. **Inbound: none, except from the control plane.**
- Secrets are injected as environment variables at session start. They are never written to disk.
- **Isolation tests** (T031):
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
`config/models.yaml`:
```yaml
roles:
  lead:          {provider: anthropic, model: claude-opus-5-5}
  extraction:    {provider: anthropic, model: claude-sonnet-5-5}
  fast_decision: {provider: typesafe,  model: jev-latest, fallback: {provider: anthropic, model: claude-haiku-4-5}}
  verifier:      {provider: openai,    model: "<set at deploy>", fallback: {provider: anthropic, model: claude-opus-5-5, prompt: verifier_independent}}
  reflection:    {provider: anthropic, model: claude-opus-5-5}
```
- Model IDs live **only** in config.
- `config.live_enabled(role)` returns false when the role's key is missing. Callers must then skip live work cleanly and log `SKIPPED_NO_KEY`. They must not fail.
- CI never calls live models.

## 10. Runner and the agent loop (`runner/`)

### 10.1 ClaudeRunner
- Uses `claude_agent_sdk.ClaudeSDKClient`, running **inside the user's box** with `cwd=/home/agent/deals/<deal_id>`.
- Options:
  - lead model from config
  - `allowed_tools` = files, bash and web tools + the in-process CRE MCP server
  - Skills loaded from `.claude/skills/`
  - `max_turns` and budget from `budget.yaml`
  - hooks (10.3)
  - subagent definitions (10.2)
- The lead system prompt is assembled from `brain/prompts/lead.md` + the firm playbook summary + user-memory retrieval + the deliverable catalog.
- The agent keeps `todo.md` (plan recitation) and `progress.md` in the deal folder.

### 10.2 Quarantined extraction subagents
- One subagent per document or document group: rent roll, T-12, OM, each lease, each third-party report.
- `tools: []`, plus an `output_format` JSON schema per document type.
- A PreToolUse hook denies any tool call that originates from a subagent, as defense in depth.
- **Pre-parse:** XLSX/CSV is read natively as cells. PDFs go through Docling, with the Reducto adapter optional and licensed. Subagents receive parsed text and tables plus page and cell anchors, never the raw file path.
- Output → `Fact`s with `claim_type=SELLER_ASSERTION` and provenance → the checksum and coverage gates.

### 10.3 Hooks (`runner/hooks.py`): the enforcement layer
| Hook | Rule |
|---|---|
| PreToolUse | Deny external actions whose toggle is off (`toggles.yaml` per user). Deny writes outside `deals/<id>/`, `outbox/`, `memory/`. Deny network to non-allowlisted domains. Deny any tool call from extraction subagents. Enforce per-task budget (turns, cost, wall-clock). |
| PreToolUse on `finalize_deliverable` | Run the deliverable's gates (Section 11). Return deny with the gate failures as feedback if any fail. |
| PostToolUse | Append an audit event. Update the cost meter. |
| PreCompact | Make sure `todo.md` and `progress.md` are current before compaction. |

### 10.4 CRE tools (in-process SDK MCP server `cre`)
- `facts_get` / `facts_put` / `assumption_set`
- `finance_run(fn, args)`
- `excel_build(template, deal)` → path
- `excel_recalc_parity(path)`
- `rules_eval(table, input)`
- `market_data(query)`
- `decide(kind, state, question)` via DecisionModel
- `ask_user(question, why, default, affects)`
- `finalize_deliverable(kind, path)`
- `draft_external(kind, to, body)` → `outbox/`
- `send_external(...)` → allowed only when the toggle is on

Tools return concise JSON with actionable error messages.

### 10.5 Ask-and-continue protocol
1. `ask_user` creates a `Question`, emits an event, records `default_used` as an `Assumption(set_by="agent")`, and links the edges to the items it `affects`.
2. The agent continues.
3. On `answer_question` from the API, the control plane updates the assumption, calls `mark_stale`, and resumes the agent session with a short message listing the stale items.
4. The agent regenerates the stale items.

The question-handling eval suite measures this end to end.

### 10.6 Screen-first fast path
- `SCREEN` runs before anything else when the request includes it or when the deal is new. Steps:
  1. classify the documents (fast_decision)
  2. extract the OM headline numbers and the summary rent roll
  3. run the buy-box
  4. emit a screen deliverable
- **Target: under 5 minutes at p50.**
- Deeper deliverables start in parallel where they don't depend on each other.

### 10.7 FakeRunner
- Replays a recorded transcript (JSONL of `AgentEvent`s and tool calls) against the real tools and gates.
- This is how CI tests the orchestration without live models.
- Record new transcripts with `cre record --task ...` when a key is present.

## 11. Gates (`gates/`), PROTECTED after M3
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
- **FastAPI:**
  - `POST /tasks`
  - `POST /tasks/{id}/answers`
  - `GET /tasks/{id}`
  - `GET /tasks/{id}/events` (SSE)
  - `GET /tasks/{id}/deliverables`
  - `POST /corrections`
  - `POST /firms/{id}/onboard`
- **DBOS:**
  - `@DBOS.workflow()` per task; steps are box resume, runner session segments, gate runs, and deliverable publish
  - a crashed task resumes from its last completed step
- **Events** are stored in the `events` table and streamed. A session can be replayed from events.
- **Budget meter** per task and per user. A hard stop emits a `BLOCKED` escalation deliverable.

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
- Traces are redacted.
- Per-tenant encryption keys are an infrastructure concern documented in HUMAN_SETUP.
- No firm's data appears in global artifacts. This is enforced by the sanitization gate plus a CI test.
- Never use LiteLLM, HyperFormula (unless licensed), Marker, or ii-agent's bundled office skills.

## 16. Observability
- OpenTelemetry spans for each tool call, model call and gate, exported to Langfuse (self-hosted) when configured.
- Per-task metrics: cost, latency per deliverable, question count, gate failures, revisions.
