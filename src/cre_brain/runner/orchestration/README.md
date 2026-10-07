# T040 helper-only handoff

This slice provides durable job helpers, a bounded stuck detector, typed host
signals, and a read-only budget view. It does not implement the analyst product
loop or T040 AC1/run acceptance. T040 remains false. Development agents are not
product analyst sessions.

## Jobs and trust

`JobStore` uses the existing canonical `jobs` table, engine, tenant filter, and
`lock_append` transaction locks. No schema, migration, alternate store, or lease
service is introduced. Uniqueness is `(user_id, firm_id, task_id, segment_no)`.
Release, deal, box, runtime, request ID, and request SHA-256 are immutable for
that key. Trusted host code must hash the complete runtime request (including
prompt, resume target, configuration and limits), not just the request label.
It must obtain all identities from authenticated host state, never the model,
request payload, or seller/user-supplied deal files.

A fresh claim records `creation_unknown` before any external action. Its
`acquired` flag denotes only the single newly reserved job; it grants no runtime
launch permission. Repeated claims do not reacquire an unknown or running job.
An expired verified running lease changes the job to `worker_unknown` and
signals recovery. Neither absent events nor elapsed leases prove a process is
absent. `mark_unknown` requires current owner and revision; receipt updates use
compare-and-swap revisions under the same task lock.

`HostReceipt` is an assertion already verified by trusted host code, not a
signature verifier or runtime adapter. `created` records `start_unknown`;
`running` requires an immutable session binding and verified ownership expiry.
Only trusted `not_started` evidence, proving no creation/start remains in flight
and no bound session exists, permits a later claim. Every job and every receipt
requires `claim_revision`, a strict integer in 1..2147483647. A newly acquired
claim sets this generation to its initial job revision; creation, running,
worker-unknown, ownership reconciliation, and terminal transitions preserve it
while the outer compare-and-swap revision increases. A later claim receives a
new generation and clears the prior receipt. Reconciliation checks generation
before replay/idempotency: even a distinct, delayed no-launch receipt from the
same owner with a newer observation timestamp and the current outer revision
cannot clear the new claim. Final completed/stopped/failed states are monotonic. A receipt cannot reconcile usage
reservations: host recovery must also reconcile canonical RunnerState events
before any future admission. Synthetic receipt tests prove helper state only;
they provide no kill, attach, resume, or production execution evidence.

The trusted runtime host must bind receipts to the claim generation issued with
the original creation/start request. It must never fill this field using the
latest job revision when consuming a delayed receipt. Missing generations in
old helper JSON fail closed; this slice invents no generation from timestamps,
lease expiry, absent events, or owner identity and adds no schema migration.

## Stuck and host actions

`StuckDetector.observe(event, now=host_now, progress=host_proof)` consumes
committed, ordered normalized `AgentEvent`s
bound to the host task/release/runtime/box/segment. Exact latest replay is a
no-op; conflicting or older replay fails closed. Identical call/result pairs,
identical errors (including tool result errors), and bounded idle events lead
to one nudge per segment, then stop/escalate. `tick` must also run on a trusted
host clock to bound silent/raw-only streams. `observe` now requires an explicit,
timezone-aware, monotonic host observation time, separately from the event.
Both event-triggered and tick-triggered nudges set the persisted watchdog
baseline (`last_progress_at`) to this host time. Thus a nudge at +10, followed
by JSON checkpoint restoration and a tick at +10, grants the full configured
interval; a 10-second watchdog stops at +20. Repeated-call/error/idle thresholds
can still stop independently after the one nudge.

Genuine host-attested committed progress resets counters and the watchdog at
its host observation time without granting another nudge or reviving a stopped
segment. Delayed progress observed at +6 uses +6 even if its event timestamp
is +5. Event timestamps and payload/model progress flags never set the host
clock or extend a deadline. Exact latest replay can advance only the observed
host clock, never the watchdog baseline; rejected clock rollback/naive time or
conflicting events leave the checkpoint unchanged. The caller must obtain
`now` from its trusted host clock, never from `event.ts`, model output, or files.

Snapshots are typed and JSON-round-trippable; history is capped, and only hashes
of call IDs/payloads are retained. No raw seller text enters emitted signals or
checkpoints. `last_signal` and the watchdog baseline survive snapshot
restoration. Old checkpoints produced by the pre-repair clock semantics need
trusted host reconciliation before reuse; this helper does not reconstruct
trusted time or receipt provenance from an old payload. The future host must
persist checkpoints and reconcile/idempotently deliver actions through the
canonical event/job lifecycle, with host acknowledgements. This slice provides
no independent checkpoint store, action executor, or action delivery guarantee.
The escalation signal contains a reason and actions, no financial/default
numbers and no fabricated ESCALATION deliverable.

## Budget integration seam

The worktree base `runner/state_adapter.py` does not expose `token_commitment`
or `require_recovered`. `budget_snapshot` therefore returns an unavailable
accounting/recovery signal by default. After T035 integration, the coordinator
must bind `CanonicalAccounting` to those canonical trusted functions (or an
explicit signature adapter), not create another meter. Both hooks receive the
same task history under `RunnerState.registry.transaction`. Recovery must
validate session/usage bindings and unknown outcomes; token commitment must
include spent plus pending reservations across the task, including earlier
releases. The helper separately validates normalized host usage as strict,
nonnegative bounded integers and checks input/output totals. Unknown accounting
is distinct from known spent/reserved usage and always blocks admission.

The budget view is advisory and does not reserve tokens. Actual admission must
use the repaired canonical `RunnerState.reserve`; the base reservation code is
not certified here. The accounting double exists only inside offline tests.

## Integration still required

Trusted runtime creation/start-or-attach receipts and process reconciliation;
CLI/intake; quarantined extraction; the lead/extract/review/revision loop;
SCR/SCREEN and UW_MODEL production; canonical publication and gates; verifier
and reflection integration; full ESCALATION publication; checkpoint/action
acknowledgements; and canonical session/usage recovery are not wired here.
No T035/T038/T039 sibling sources were read, copied, or changed. No existing
tracked source, guards, tests, feature flags, PROGRESS, Git state, or dependencies
were changed. No network services, live models, private evaluations, or
production transcripts were exercised.

## Verification

Tests were written first. Initial collection failed on missing helper modules.
Additional state tests failed on stale no-launch receipt reuse, unconstrained
unknown-phase transitions, receipt replay bypassing revision validation,
missing silent-stream watchdog, repeated tool errors, and delayed committed
progress. Those failures were corrected in the helper sources.

The independent SOURCE FAIL findings were reproduced red-first as exact state
regressions: W1/R1/R2 followed by same-owner W2 accepted the distinct delayed R2;
and identical errors at +8/+10 nudged before a JSON roundtrip/tick at +10
immediately stopped. Both tests now pass. Additional tests cover generation
persistence, required/strict Python and JSON generation bounds, missing and
conflicting generations, valid new-generation receipts, explicit host-clock
input, clock rollback, future event timestamps, and replay without deadline
extension. Only the new jobs/stuck helpers, their own focused tests, and this
README changed for these repairs.

Focused offline SQLite/synthetic suite after the two review repairs:
**79 passed, 1 integration deselected**.
Existing canonical event/store and tool regression tests: **75 passed**
(with two dependency deprecation warnings).
Ruff check/format and strict mypy on all four new source modules passed.
The coordinator owns setup, full `make check`, and PostgreSQL execution. The
PostgreSQL test reuses `tests/state/test_t011_postgres.py`'s fresh isolated-schema
fixture; it was deliberately not run in this offline worktree. The exact T040
verifier/task checker was not run, and these tests do not claim full AC coverage.

```bash
UV_CACHE_DIR=/tmp/t040-uv-cache uv run --offline --no-sync pytest \
  tests/runner/test_t040_jobs_core.py tests/runner/test_t040_stuck_core.py \
  -q -m 'not integration' --basetemp=/tmp/t040-p1p2-final-20261005-01
UV_CACHE_DIR=/tmp/t040-uv-cache uv run --offline --no-sync ruff check \
  src/cre_brain/control/jobs.py src/cre_brain/runner/orchestration \
  tests/runner/test_t040_jobs_core.py tests/runner/test_t040_stuck_core.py
UV_CACHE_DIR=/tmp/t040-uv-cache uv run --offline --no-sync ruff format --check \
  src/cre_brain/control/jobs.py src/cre_brain/runner/orchestration \
  tests/runner/test_t040_jobs_core.py tests/runner/test_t040_stuck_core.py
UV_CACHE_DIR=/tmp/t040-uv-cache uv run --offline --no-sync mypy --strict \
  src/cre_brain/control/jobs.py src/cre_brain/runner/orchestration
```

Use a new unique basetemp for each subsequent pytest invocation. With the
coordinator's test-only PostgreSQL URL configured, run the integration test
separately using `-m integration`; never substitute a production database.
