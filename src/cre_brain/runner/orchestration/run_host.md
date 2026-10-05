# Bounded local run host contract

This is a supported **SCREEN composition subset**, not full T040 acceptance.
`feature_list.json` remains false. All run-slice tests use synthetic/partial names outside the T040 acceptance
namespace; they prove public plumbing only. No native runtime, container configuration, transcript,
PostgreSQL recovery, live analyst quality or private evaluation evidence was
produced by this slice.

`cre run --deal <absolute selector> --request <bounded text>` is registered
explicitly in `cre_brain/cli.py` through `runner/run_commands.py`, alongside
`record_commands.py` and `tools_commands.py`. It does not change package plugin
discovery or register commands when `create_app(plugins=[])` is used. The default
returns `missing_runtime`. Only trusted embedding code can call
`runner.run_commands.install_run_host(RunHost(...))`; neither environment
variables nor module paths nor files in a deal install runtime code.

## Required host composition

- `authorize(RunInput) -> RunPlan` authenticates the tenant and selects immutable
  task/deal/release/box/request identities and policy. It performs bounded local
  selection only, never provisioning, staging or launching a model session.
  The deal argument is a selector, not authority for filesystem roots.
- The plan pins the exact request and segment, workspace, expected runtime
  capabilities, deterministic parsed sources, trusted semantic selections and
  reconciliations, document descriptors and canonical SCREEN references. It
  includes the `configuration_digest` of settings, limits, generated instructions,
  roots, extraction configuration, risk/buy-box policy and gate settings/as-of.
  Complete serialized plans use the existing bounded canonical JSON contract
  (128 KiB). Unsupported intake fails closed.
- `compose(plan, job) -> RunSession` runs **after** a durable claim, or for a
  completed replay. It constructs existing Preparser, Extractor, CodexRunner and
  ScreenService objects over the same authenticated ToolRegistry and engine. It
  must not start a lead. Raw/parsed roots and the isolated box must already exist.
- The injected streaming adapter extends the existing `StreamingAdapter`
  structurally with a typed immutable `claim_binding: NativeClaim`. Native
  launch/cleanup evidence must retain that identity, owner and original claim
  generation. The adapter must expose the same canonical registry through its
  isolated MCP transport and stage only trusted instructions and canonical typed
  facts/references. There is no host subprocess fallback or default adapter.
- Before exposing tools, compose installs `RunGateService` on that same registry,
  using the existing GateService authority/settings/as-of and the claimed job.
  The gate wrapper delegates every verdict to the existing gates. Separately,
  run orchestration binds `RunPublicationAuthority` once on that registry before
  exposing the runtime. Generic finalization enforces this authority before
  publication, immediately before the protected transition, and on all checked
  final-release reads, existing-final and idempotent replay. Changing the gate
  provider cannot remove this restriction. Registry clones retain it; a different
  lifecycle authority requires authenticated recomposition, never replacement.
- `ReceiptVerifier.verify(job)` must independently verify the actual native
  outcome against the original claim generation and exact session/request. A
  parsed agent response or absence of events is not verification. The returned
  HostReceipt must agree with the canonical segment end, usage completion and
  session binding. A session-less stopped receipt requires host proof of absence
  of an assigned session; it cannot substitute a guessed session ID.
- `HostControls.nudge(job)` must acknowledge delivery to the actual claimed
  runtime. `RunHost.clock` supplies aware UTC receipt/claim observation time only.
  The watchdog uses real `time.monotonic()` elapsed time, mapped onto a fixed UTC
  baseline for the unchanged reviewed StuckDetector interface. Wall-clock jumps
  cannot accelerate its deadlines. Nudge acknowledgement starts a full new silent
  or no-progress interval; all subsequent committed events still reach `observe`,
  retaining the helper's discrete repeated-event stop behavior. Checkpoints record
  their monotonic elapsed basis. Agent clocks/progress claims are untrusted.

## Supported flow and safety boundaries

After claim and binding validation, real deterministic preparse must reproduce
each exact host source pin. Source/configuration/claim/gate pins are rechecked
after capability awaits before extraction, across extraction staging/capability
awaits, after extraction before lead admission, and across the lead's own awaited
capabilities/staging before native start. Secure no-follow source byte reads
recheck raw bytes on these boundaries. Trusted native adapters retain their
atomic configuration/launch obligation inside `start`; arbitrary replacement of
all trusted Python code is outside this boundary. The existing Extractor owns quarantine, canonical
seller facts, coverage/checksum checks, reservations and bounded cleanup.
CodexRunner then owns one segment's atomic RunnerState reservation, streaming,
usage reconciliation and bounded native cleanup. One task consumes its entire
async generator so its timeout remains valid across yields. A separate watcher
continues ticking during silent streams and stops after nudge plus a full interval.

After native receipt verification returns, exact transport/registry/context,
source bytes and configuration bindings are revalidated before reading tenant
lifecycle evidence or reconciling terminal job status. This also applies to
stopped and failed receipts. Canonical `require_recovered`/`token_commitment`
checks then precede terminal job reconciliation. Only completed runs build SCREEN, call the
existing finalizer, authenticate protected publications and persist a small
publication manifest in canonical events. The compact manifest pins each exact
original final version, protected publication row reference, path, body SHA-256
and size. Source/configuration pins are checked again before publication. No second usage ledger or publication store exists.

Completed replay rechecks the same host bindings, exact sources, canonical
freshness, exact original versions/references/hashes, blocking results and
protected release bytes. A newer authorized revision under the same ID is
`publication_changed`, never silently returned under the old run manifest. It
launches neither extraction nor another lead. It currently requires restored
trusted artifact descriptors and the current artifact mirrors, as required by
existing finalization replay. Historical protected retrieval remains a separate
existing interface.

Cancellation propagates after bounded cleanup even if cleanup fails. Unknown
start, cleanup, receipt or usage outcomes remain nonterminal and prevent a fresh
launch. Extraction batch/nudge/receipt tasks are owned by persistent
`RunHost.operations`, cancelled
and boundedly drained on timeout/cancellation. Unknown operations remain marked
for recovery even if they later finish; late completion is not native evidence.
The synchronous CLI uses a dedicated loop rather than `asyncio.run`'s unbounded
shutdown cancellation wait. A still-pending loop stays retained under that same
host owner; embedding must supervise recovery or terminate its isolated worker.
Retention does not automatically resume a loop. Python cancellation is
cooperative: a trusted coroutine that suppresses cancellation cannot be forcibly
terminated here. Native adapters remain responsible for bounded cleanup.

The batch observation window uses the configured per-document timeout multiplied
by the number of parallel waves, capped by the remaining canonical task time.
Observation and cancellation drain use `asyncio.wait`, so a document stage or
the existing quarantine batch drain cannot indefinitely hold the run caller.
The exact healthy observed batch is recognized by its extraction guard; unknown
operation markers and other unresolved tasks remain barriers. A pending batch
retains ownership of its document tasks and child drain. Its known boxes are not
claimed destroyed at return. Quarantine still owns actual cancellation,
destruction, reservations and accounting. Even successful late destruction cannot
remove the host recovery marker or authorize another session. Settled operation
buckets are removed when empty; separate recovery markers remain intact.

Unexpected host programmer faults retain bounded diagnostics containing only
exception type, stage and source module/function/line, never raw messages, locals, seller
content or secrets. Legacy ValueError receipt refusals also retain these safe
diagnostics. A crash between native completion and the checked publication manifest
refuses recovery; it does not rerun SCREEN or create a duplicate native session.
One shared process wrapper captures faults during stdout opening/iteration,
wait and cancel for lead and extraction before the existing handlers erase them.
It rethrows original failures and leaves cancellation and native receipt semantics
unchanged. Diagnostics retain at most eight frames and 128 recent faults.

## Exact remaining seams for the coordinator

1. T035 stores document-scoped semantic keys; SCREEN requires canonical headlines
   including DSCR, occupancy and market tier. This slice requires independently
   authenticated stored headline pins. It does not rename extracted facts,
   calculate missing headlines, invent verification or upgrade seller assertions.
2. A real host must implement authenticated isolated streaming/MCP staging,
   claim-bound native receipt verification and nudge delivery, and preserve the
   trusted plan/authority/artifact bindings across process restart. Synthetic
   adapters exercise transport only. These native capabilities remain unverified.
3. Active/unknown/stopped/failed recovery, attach, new authorized segment numbers,
   partial-publication recovery and restored watchdog continuation are deliberately
   `recovery_unavailable`. Stored checkpoints do not themselves authorize resume.
4. Budget/watchdog/stopped paths return `escalation_unavailable` with a typed
   reason. No ESCALATION is falsely presented as published. Canonical question
   defaults and an authenticated escalation artifact/plan/finalization composition
   are still needed; no numerical defaults or gate verdicts are invented here.
5. UW requests return `unsupported_underwriting` before a claim or factory call.
   T039's Python model and draft workbook are not published UW_MODEL evidence.
   Complete paired gates/protected publication and broader workbook support remain
   integration work.
6. Full T040 runtime/eval acceptance and full coordinator checks remain outstanding.
   Existing T040 helpers, assertions, flags, owner guards and transcripts remain
   unchanged. Four existing partial test functions were renamed out of the
   acceptance namespace as requested. The owner-authorized canonical API changes
   are generic bind-once publication authorization in registry/finalization; all
   run lifecycle policy remains in orchestration. No Git, network, setup, cloud,
   live model or private-eval work ran.

## Final local verification (2026-10-05)

Tests were written before implementation: the initial CLI tests failed (missing
command/module), and core collection failed (missing run module). Additional
red-first regressions caught lost parent cancellation on failed cleanup,
per-iteration task ownership breaking the native deadline, missing native claim
pins, changed source bytes after lead launch, an orphan producer after a failed
checkpoint, and a shortened interval after slow nudge delivery. Final green
verification follows; no existing assertion was changed.

```bash
.venv/bin/python -m pytest tests/runner/test_run_loop.py tests/runner/test_run_loop_cli.py tests/runner/test_t040_jobs_core.py tests/runner/test_t040_stuck_core.py tests/runner/test_codex_t033.py tests/deliverables/test_screen.py tests/extraction/test_quarantine.py -q -m 'not integration' --basetemp=/tmp/run-loop-focused-final-20261005-02
```

**343 passed, 1 deselected, 2 dependency deprecation warnings, 75.19 seconds.**
This includes all 31 new run/CLI tests and existing jobs, watchdog, Codex,
SCREEN and quarantine regressions. The deselected test is the existing
PostgreSQL integration case; coordinator PostgreSQL evidence remains separate.

```bash
.venv/bin/ruff check src/cre_brain/runner/orchestration/run.py src/cre_brain/runner/cli_run.py tests/runner/test_run_loop.py tests/runner/test_run_loop_cli.py
.venv/bin/ruff format --check src/cre_brain/runner/orchestration/run.py src/cre_brain/runner/cli_run.py tests/runner/test_run_loop.py tests/runner/test_run_loop_cli.py
.venv/bin/python -m mypy --strict src
```

Ruff: **all checks passed**, **4 files already formatted**.
Strict mypy: **143 source files pass**. Every pytest invocation used its own
unique basetemp. Full `make check`, T040 verify/check_task, native/live runtime,
private evals, Git, commit and push were not run.

The historical checks above used the registrar's former filename. Its current
source is `runner/run_commands.py`; no `cli_*` compatibility module remains.


## Independent SOURCE FAIL repair evidence (2026-10-05)

The initial review regression run used
`/tmp/run-loop-review-red-20261005-01`: **15 failed, 1 passed** (10.74s).
It exposed drift before extraction/lead start, gate replacement publication,
version-only replay, lost host tasks, ignored post-nudge events, acceptance-name
leakage and missing fault diagnostics. Two new probe harnesses needed correction:
prior publication inventory/accounting and waiting for lead start in the clock
probe. Corrected targeted probes failed as expected; the lifecycle replay harness
now directly binds an unknown claim, avoiding unrelated budget admission.

Additional red-first checks: the CLI `asyncio.run` prohibition (**1 failed**, temp
`/tmp/run-loop-review-cli-red-20261005-05`), missing receipt ValueError diagnostics
(**1 failed**, `/tmp/run-loop-review-diag-red-20261005-07`), and extraction
capability drift before native extraction start (**1 failed**,
`/tmp/run-loop-review-extract-red-20261005-10`). A negative-control run disabled
only the generic publication authorization hook in memory and reproduced **both**
existing-final/idempotent final replies under `creation_unknown` (**1 failed**,
`/tmp/run-loop-review-replay-barrier-negative-20261005-12`). No production source,
existing assertion or feature flag was changed for this negative control.

The run/CLI green run passed **50 tests** (32.22s, temp
`/tmp/run-loop-review-green-20261005-09`). After adding extraction-await and
lead-stage drift regressions, the review file passed **21 tests** (14.52s, temp
`/tmp/run-loop-review-extract-green-20261005-11`). Final expanded verification is
recorded below. These are synthetic plumbing checks, never T040 acceptance.

## Five-defect repair handoff (2026-10-05)

New additive regressions are in `tests/runner/test_run_loop_repairs.py`. The first
run reproduced all five findings: **22 failures**, including the two unchanged
plugin-discovery assertions. Receipt tests include completed/stopped/failed
outcomes, another tenant's matching completed ledger while the original tenant
retains an unresolved reservation, and checks that drift is rejected before any
post-verification lifecycle read. Source/configuration and exact registry identity
are pinned. An additional registry-clone variant reproduced **three failures**
before adding its identity check.

Extraction tests run the real quarantine batch and `_one` with a stage that
suppresses cancellation. Timeout and parent cancellation return while the exact
batch remains owned, the original reservation remains unresolved, and its known
box has not been destroyed. CLI coverage retains that loop until the synthetic
stage is manually released; late destruction preserves recovery ownership and
does not start a model. Process diagnostics cover stdout invocation/iteration,
wait and cancel in both runtimes, and cancel faults during parent cancellation.
Bucket tests cover 200 successful distinct jobs, settlement alongside another
live operation and late settlement of an unknown operation.

Existing run-loop tests changed only their registrar imports and resulting import
ordering. Their assertions, the two existing plugin assertions, owner guards and
all task flags remain intact. Final focused commands/results and intermediate
failures are appended to `PROGRESS.md`. Full `make check`, independent rereview and
the subsequent complexity audit belong to the coordinator/owner. The duplicate
lifecycle predicates were not refactored in this repair slice. Standalone
Extractor callers retain their existing cooperative batch-drain contract; the
hard observation/ownership boundary here applies to the guarded run candidate.
Genuine runtime, trusted recovery/attach, checked UW/ESCALATION publication,
advisory review/revision and quality/eval evidence remain outstanding.
