# T032 host composition and tool contract

`ToolRegistry` is the single implementation behind `cre tool NAME --args JSON`
and `cre mcp serve`. The explicit builtin registrar is `tools_commands.py`.
No runtime extras are imported to display root help. Standalone invocations
refuse with `missing_context`: the authenticated launcher must call
`install_host_factory` before entering `cre_brain.cli.main`. Tool arguments,
environment variables and deal files cannot install a factory or providers.

The host supplies an existing state engine, `HostContext` (authenticated
TenantScope/task/deal/role/session/start), validated Settings/Limits, a private
workspace, and the `InputProvider` protocol from `contracts.py`. Host source
anchors must authenticate exact source versions and verification/user authority;
provenance or seller assertions alone do not confer authority. Quarantine is
supported and cannot feed finance. Anchors are immutable source-version IDs.
State/database credentials and host provider composition must remain outside
analyst mounts. These unit tests do not prove that infrastructure boundary.

Every numeric argument is a `Reference` with kind, record_id, current version,
key and unit. Decimal fact values use the existing tagged domain encoding.
`finance_run` currently whitelists build_proforma, calculate_exit,
calculate_returns (including dated flows), excel_npv and cash_on_cash. Inputs
and all outputs come from deterministic finance code. Calc IDs include the
scoped deal, ordered field references and a hash of installed finance sources.
CalcResult.inputs and graph edges contain the actual source identities; the
trusted binding event also stores field_references and the typed finance_input
snapshot for host gate adapters. A later source version invalidates descendants.
Assumptions receive fresh immutable identities on revision; the response returns
record_id/version/unit for later finance references. ask_user records the
question, default assumption and affected deliverable edges and returns at once.
Answer/resume endpoint wiring remains with the control-plane coordinator.

`InputProvider.artifact` authenticates canonical Deliverable identity, kind,
version, deal, bytes hash and extraction classification. A separate
`GateProvider` with authenticated scope and check(name, deliverable) implements
the small GateService seam. The tool selects every required SPEC gate, including
extraction coverage/checksums, and treats only entailment/verifier as advisory.
Missing/invalid providers, malformed verdicts, failures, changed bytes, stale
state or elapsed session deadlines refuse release. Gate results and the final
append-only transition are persisted in one scoped transaction. Release replay
checks the current final version and artifact bytes. A newer draft needs a new
request ID. T037 source was read only to align this seam; its current service is
not imported or certified safe. The coordinator must adapt its repaired evidence
provider to the stored field references, finance input snapshots and direct
CalcResult lineage before installing it here.

Excel accepts only the host's hash-pinned mapped mf_standard reference template
and stored trusted proforma inputs. It stores a server-created WorkbookBuild;
recalc accepts its artifact ID, never an uploaded descriptor/expectation/PASS.
Only an injected host ExcelEngine can recalculate. The deterministic Excel
checker determines parity; an engine that does nothing fails cached-value checks.
The current reference template requires mapped Facts, including a stored count
for projection_months, and excludes optional tax/value-add schedules. The host
must protect reference templates and tool work directories from concurrent
analyst writes and provide an isolated recalc engine. No engine/containment/live
proof is inferred from these tests.

Drafts are plain local JSON, written exclusively under
outbox/deal/task. Recipients are configured IDs, not model-issued addresses.
Sending obeys host off/ask/on toggles (default OFF). Ask returns a durable cid and
confirmation_request immediately. Only the host's authenticated confirmation
endpoint may invoke confirm; there is no confirmation tool or caller PASS field.
Even an enabled/confirmed send needs an allowlisted tenant connector and a body
that exactly matches a gate-finalized canonical LOI or BROKER_QUESTIONS artifact.
The send intent commits before the connector runs. Concurrent/repeated attempts
cannot resend; an uncertain outcome requires host reconciliation. Connectors
must also honor the stable tenant/task/draft idempotency key. Offline tests never
send externally or verify a real connector.

Tool usage, session snapshots, host-reported token usage, confirmations and replay
responses persist in existing scoped event tables. Calls serialize with SQLite
BEGIN IMMEDIATE in tests or tenant advisory locks in PostgreSQL; graph/event
locks coordinate the existing state interfaces. Host state writers must honor
these locks and invalidate graph descendants. Caps are task/session scoped;
the box/control plane remains responsible for account-wide nightly limits,
active process limits and terminating blocked processes. Failed calls count
against the durable tool budget; the tool checks deadlines again before release
or reserving delivery. Host record_host_tokens supplies authenticated usage.

Canonical JSON is sorted, ASCII and compact, bounded to 128 KiB and depth 20.
Duplicate keys/nonfinite values/extra authority fields are rejected. Low-level
provider/SQL/filesystem/serializer diagnostics are withheld; errors use stable
categories and remediation text. File reads traverse no-follow directories,
reject hard links/symlinks and cap regular files at 16 MiB. Outbox writes are
exclusive. Orphan files after an interrupted write require host reconciliation.
OS isolation, private mounts and process termination remain required host
controls, especially while path-based Excel libraries execute.

The minimal stdio implementation uses one JSON-RPC 2.0 object per line. It
supports initialize for 2024-11-05/2025-03-26/2025-06-18, notifications, ping,
tools/list and tools/call. Results contain canonical CLI JSON in text content;
refusals set isError. Pass a retry ID in tools/call params._meta["cre/request_id"]
(the CLI equivalent is --request-id). With no explicit ID, mutations derive a
stable content ID. The transport exposes no resources/prompts/sampling/HTTP.
Offline parity/framing tests are plumbing evidence, not live MCP/Codex protocol,
T030 profile verification, analyst quality or runtime containment evidence.
