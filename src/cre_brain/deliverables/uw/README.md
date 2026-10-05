# Independent T039 core handoff

This is a host-only Python composition slice at local dev `22d4dc7`. It is not
an analyst command, publication store, gate service, SCREEN implementation or
complete T039 acceptance. No underwrite skill is installed: its commands do not
exist yet. The coordinator must integrate reviewed T038 interfaces first.

## Interfaces

`UWCore(registry: ToolRegistry).compose(UWRequest) -> UWModel | UWRefusal`
uses the existing registry's authenticated context, transaction, policy budget,
SQL records, bindings and dependency edges. Numeric assumptions are supported; categorical/date assumptions are outside
this slice and refuse. Every financial input is a T032
`Reference(kind, record_id, version, key, unit)`, never a literal numeric value.
`UWRequest` has proforma reference fields and optional tax, value_add, debt and
returns components. A requested component requires its complete input set;
missing or extra fields produce typed questions. No implied financial defaults
are added. Supply optional components explicitly when their evidence exists.

Exact accepted fields and units are in `calculations.py`'s `*_UNITS` contracts.
The proforma uses all eight existing `build_proforma` inputs. Tax inputs require
explicit `annual_growth_cap` (a ratio reference or explicit `None` meaning no
cap) and a boolean evidence reference `operating_expenses_exclude_property_tax`.
This must resolve to true to avoid counting tax twice. Projection years derive
from the supplied monthly horizon. Value-add uses the existing `ValueAddPlan`, with an explicit computational
support limit of 600 renovation cohorts (larger plans refuse before execution).
Debt uses the complete existing `LoanTerms` plus property_value, max_ltv,
min_dscr and min_debt_yield; annual_noi is the persisted first full year of the
composed proforma, with a canonical output reference. Returns accepts only the
existing T032 `FinanceRun(fn="calculate_returns", args=...)` contract, including
its supported dated-flow references. Returns do not imply an exit calculation
or generate equity cash flows. All money arithmetic remains inside the existing
finance library's isolated Decimal/Fraction semantics.

Canonical calculations are append-only SQL `CalcResult`s, with a hash of finance
implementation files (existing T032 functions) or finance plus UW implementation
files (composition functions), exact input record identities and scoped binding
events. Existing identities are recomputed and compared before reuse. Typed
output references also carry output key, source version and unit. Evidence
snapshots retain source records, assumption ranges/rationale/proxy flags,
provenance, versions and binding metadata. They are immutable tuples and JSON
strings, with no mutable numeric dictionaries. `UWModel.model_dump_json()` is
the serializable Python-model artifact; the model and its snapshots are not a
second authoritative store. `calculation(component).output(key)` returns a
`ModelNumber(value, reference)`.

`UWCore.workbook(UWModel) -> UWWorkbook | UWRefusal` revalidates stored evidence
and model numbers, then delegates build and recalculation to existing T032
handlers. It returns a draft artifact ID, actual saved recalculated path and
stored digest only after complete existing parity succeeds. It accepts no PASS
value or caller-selected gates, and does not finalize or publish anything.

## Base limitations and T038 integration

At this base, there is no `ExcelBuildSpec` symbol: the actual existing contracts
are `ExcelBuild`, trusted `Template`/`TemplateMap`, and `WorkbookBuild`. The
existing generated mf_standard mapping supports only mapped Fact inputs and a
60-month unlevered proforma without optional schedules. The writer independently
recomputes that subset and rejects nonzero tax/value-add impacts. Assumptions,
other horizons, optional tax/value-add schedules, debt and returns therefore
produce `unsupported_workbook` rather than a partial workbook presented as
whole-model parity. A reviewed template/writer extension is still needed for
that broader mirror; this slice writes no additional spreadsheet formulas.

The base recalculation handler stores the saved output digest but omits its
path. The core resolves exactly one digest-matching `.xlsx` inside the exclusive
artifact directory. It refuses missing or ambiguous matches. T038's canonical
paired-finalization interface should consume the explicit Python snapshot and
saved workbook identity/path/digest instead of repeating this lookup.

Required coordinator work:

- Integrate T038's canonical risk_score composition and actual risk evidence.
- Authenticate paired Python/Excel finalization through T037/T038 trusted gates,
  including checksums, assumption_ranges, irr_sanity, fragility and provenance.
- Persist/publish through T038's reviewed storage implementation, not this module.
- Add supported underwrite commands/skill and SCREEN + UW FakeRunner composition.
- Run full required checks and complete acceptance only after those interfaces
  and broader workbook gaps are resolved. All T039 flags remain false.

Undefined/ambiguous IRRs are explicitly labelled; this core emits no investment
recommendation, even when the supplied flows have a unique root. Typed refusal
questions are returned to the host without inventing a Question.default_used
or a financial assumption. The coordinator can route them to its question flow.

## Worktree verification (2026-10-05)

- Red-first collection failed with missing `cre_brain.deliverables.uw`; the
  later snapshot-tamper regression failed before its authenticity check was
  added (`missing_provider` instead of `untrusted_evidence`). Logs are local
  `.cache/t039-red.log` and `.cache/t039-tamper-red.log`. Additional red-first
  regressions cover the cohort execution bound and persisting an explicit
  uncapped-tax marker, in `.cache/t039-cohort-red.log` and
  `.cache/t039-null-manifest-red.log`.
- `.venv/bin/python -m pytest tests/deliverables/test_uw_core.py tests/finance
  tests/excel -q -m 'not integration'`: **363 passed, 1 skipped, 5 deselected**.
  Final log: `.cache/t039-focused-final.log`. The skip is the existing
  approved MS_GRAPH licence test. The deselections are
  the new real UW UNO test and four existing native Excel integration tests.
- `ruff check` and `ruff format --check` on UW source and tests pass.
- `.venv/bin/python -m mypy --strict src`: **123 source files pass**.
- Running the whole new UW file with real configured LibreOffice/UNO produced
  **15 passed, 1 failed**, with no skips: the real recalculation test failed
  (before the final uncapped-tax manifest regression was added).
  T032's handler returned `provider_error`; direct native diagnosis showed
  **Office exited before UNO connection (exit 1)**. Its only captured Office
  stderr was the javaldx warning. `strace` was unavailable under the sandbox
  (`PTRACE_TRACEME: Operation not permitted`). The underlying startup cause
  remains unresolved; no recalculated workbook or passing parity is claimed.
  The real test is retained, not skipped or weakened. Coordinator must rerun it.
- `/usr/bin/soffice` is absent; real testing used the coordinator's already
  extracted public LibreOffice runtime configured through environment (the
  existing `/tmp/cre-excel-runtime-env.sh`) and `/usr/bin/python3`. No daemon or
  container runtime was started. The existing engine owns short-lived Office
  subprocesses and isolated temporary HOME/profile/TMPDIR paths.
- `./init.sh` was attempted offline with a worktree-local `.venv` and cache and
  its Git-hook installation disabled to honor the no-Git-change constraint.
  It failed because cached wheels were unavailable (first scipy, later
  pre-commit). Verification used local copies of the coordinator main checkout's
  pinned **third-party package files only**, excluding editable package paths
  and `.pth` files; a new local source `.pth` targets this worktree. No T038
  checkout, environment, credentials, caches or native homes were used. No
  dependency pins or lock files were changed. Setup is not claimed complete.
- Full `make check`, task acceptance checks, live models, network, private evals,
  commits and promotion were not run. Existing tracked files, owner guards,
  PROGRESS and feature flags remain unchanged. Final type-check log is `.cache/t039-mypy-final.log`;
  the retained real-runtime failure is `.cache/t039-uw-final-native.log`.

## Core review repairs (2026-10-05)

Assumptions must be the active host-bound identity for the authenticated tenant's
same deal/key, with the current source version and compatible unit. Replacing
3% with 5% refuses the old identity even when it has no calculation descendants;
the replacement and an untouched assumption remain usable. These checks apply
transitively to stored calculation dependencies and workbook revalidation.

Composition charges one host tool call inside the outer transaction. Typed
refusals and invalid request boundaries commit that charge; exhausted caps and
invalid host policy refuse before charging. All calculation records, dependency
edges and calculation binding events use one inner savepoint and roll back
together on failure. The registry deadline runs after all composition and
snapshot work, immediately before successful savepoint release/return. An
expired call retains its usage charge but persists no calculation writes.

Request field sets and sequence cardinalities are validated before source
inspection. Unsupported components/fields and missing fields produce typed
refusals. Proforma/tax/value-add/debt dictionaries support exactly 8/9/8/12
fields respectively; returns require the existing three fields plus optional
ordered dates, with 2–600 cash flows, matching dates and scalar rate references.

Computational limits are checked before calling finance functions:

- Existing proforma support remains 1–360 months; taxes derive at most 30 years
  from that same explicit horizon. Existing loan term/amortization/IO limits
  remain 600 months, with the existing sign and IO consistency requirements.
- Value-add supports at most 600 cohorts and requires its start inside the
  supplied projection. The monthly/cohort loop therefore visits at most
  360 × 600 combinations. Unit counts have no added property-size ceiling;
  downtime and ramp counts remain arithmetic inputs, not loop horizons.
- Returns retain the library's 600-flow support and refuse nonconventional IRR
  above 128 distinct nonzero periods/dates before library execution. Exact
  aggregation preserves repeated-date cancellation; IRR classification,
  ambiguity, refusal and deterministic calculation reuse remain library-owned.
- Evidence inspection supports 2,048 supplied references and 2,048 reachable
  reference identities, 4,096 dependency edges, depth 20 and 16,384 expanded resolver visits per inspection. Preflight
  bounds the full graph, including repeated-edge expansion, before invoking
  the shared recursive resolver. Visited references are deduplicated before
  resolution. Cycles refuse as stale evidence; other traversal support limits
  produce `unsupported_inputs`.
- Host-only binding snapshots support 1 MiB each, separately from the unchanged
  shared tool-message byte limit. This preserves the full 360-month projection.
  Numeric values retain the existing T032 finite Decimal digit/exponent bounds.

No financial defaults or model arithmetic were added. Only this core, its
candidate tests and this README were edited. Shared T038, baseline assertions,
Git metadata, PROGRESS, feature flags and protected files remain untouched.

Regression evidence is in `.cache/t039-review-red.log` (15 failed, 8 passed),
`.cache/t039-bounds-red.log` (5 failed, 2 passed),
`.cache/t039-range.log` (full-horizon regression), and
`.cache/t039-returns-red.log` (library execution-order regression). Green results
and the exact verifier outcome are recorded below after the final runs.

Final focused run:
`.venv/bin/python -m pytest tests/deliverables tests/finance tests/excel -q -m 'not integration' --basetemp=/tmp/t039-review-focused-04`
passed **404 tests**, with **1 existing approved MS_GRAPH licence skip** and
**5 integration deselections**. Log: `.cache/t039-review-focused-last.log`.
Ruff check/format checks pass for UW source and candidate tests; strict mypy
passes all **123 source files**. Each pytest invocation used its own basetemp;
the acceptance checker also creates an exclusive temporary directory.

The exact T039 verifier was run offline with synchronization disabled, using the
existing configured native runtime; it exits **1** on the real UW UNO test
(`provider_error`). A second attempt using the native Office binary also failed.
The final exact-command log is `.cache/t039-review-exact-final.log`.
The separately invoked unchanged `check_task.py T039` exits **1**, reporting
**4 passed, 1 native-test failure**, and **missing AC3**;
log: `.cache/t039-review-task.log`. No integration assertion or approved marker
was altered. The owner's report of 17 passing coordinator UNO tests after clean
entrypoints is separate evidence; this worktree has not reproduced it with the
previous environment file. Full coordinator checks remain coordinator work.

T039 remains **false**. Risk composition, authenticated paired finalization,
FakeRunner/skill acceptance and the broader workbook mirror remain required
integration work; these repairs make no claim of complete task acceptance.

## Coordinator stable-runtime re-verification (2026-10-05)

The coordinator used the approved persistent runtime helper
`/root/work/cre/codex-20261004/excel-runtime-env.sh`, not the earlier `/tmp`
helper. The unchanged final UW tests, including genuine UNO recalculation,
passed: **58 passed**, no skips, in 79.40s. Log:
`/root/work/cre/codex-20261004/t039-coordinator-stable-native.log`.
This supersedes the earlier environment-specific provider failure, not the
unsupported full-model workbook limitations above.

The unchanged `check_task.py T039` now reports **5 passed** and exits **1 solely
for missing AC3**. Log:
`/root/work/cre/codex-20261004/t039-coordinator-stable-verifier.log`.
The independent GPT-6.1 Sol final source review returned **SOURCE PASS** for this
host-only slice after 46 in-memory cases and five adversarial probes. It did not
run native UNO itself. Full publication, risk integration, underwrite commands,
skill/FakeRunner acceptance and the broader mirror remain incomplete; T039 is
still false.
