# Quarantined extraction source plumbing (T035)

`Extractor.extract(tuple_of_doc_ids)` is a host-only composition seam. It resolves
`SourceProvider` records using the canonical registry's authenticated context;
there is no extractor tool accepting document JSON, model settings or gate plans.
One bounded disposable box receives exactly one authenticated immutable
`ParsedDocument`. The host generates the schema/config and an argv tuple for
`codex exec --json -p extractor --output-schema ...`. No buffered execution or
host subprocess fallback exists.

The three Pydantic schemas cover rent-roll, T-12 and OM-summary observations.
Values and quotes are exact source lexemes tied to immutable source anchor IDs.
The host requires an independently approved semantic anchor inventory and source
component/total reconciliations. Missing totals/inventories, formulas/caches,
ambiguous dates/numbers and incomplete parsing refuse. Native numeric lexemes use
Decimal; formatted numbers use the existing deterministic numeric parser. Only
unambiguous ISO calendar dates are supported. Text remains byte-for-byte decoded
source text. No model arithmetic, inferred numbers, verification or finance
permission is granted.

Facts remain `SELLER_ASSERTION`, with tenant-scoped canonical storage, deal/document
provenance and quarantine bindings. Both existing T037 gates inspect one immutable
host artifact snapshot in the same canonical transaction as new Facts. The narrow
`gates/state.py` and `state/graph.py` read seams bind those existing checks to
`ToolState.connection`, including the unchanged canonical stale-item checker; no alternate gate/state implementation is introduced.
The whole batch rolls back on a conversion/gate failure. Input and result order
are deterministic; live boxes obey `max_parallel_extractions`.

Attempts, native token accounting and accepted snapshot digests live in existing
canonical events. Exact retries recheck current Facts, bindings, freshness and
gates without another box. Different source bytes under an existing semantic
identity refuse; intake must issue a new document identity for a revised source.
Crashed attempts and unknown cancellation/destruction receipts require host
recovery. Cancellation drains all started boxes, including repeated interrupts.
Synthetic runtime evidence requires explicit test-only composition and cannot
be reused by the production default.

## Blocked prerequisites

T035 is not accepted by this source work. T033 still requires coordinator/owner
acceptance of its reviewed source candidate. No concrete owner-provided bounded
extraction runtime adapter is implemented or exercised here. T031's buffered
`create_extraction` seam alone cannot prove CLI/schema/config inventory, private
authentication with safe concurrency, no MCP/ambient plugins, immutable one-file
mounts, model-only egress, preventive usage caps, or descendant cleanup.
`ExtractionRuntime` requires independently verified bindings after staging in the
same box and must enforce these conditions before every model call. An adapter
that is missing/unverified refuses. T034 source authentication and host-approved
semantic/reconciliation inventories must be supplied by intake.

The tests use explicit public synthetic ParsedDocuments and in-memory provider
records. The AC4 temporary capture is produced by T033's recorder and replayed
through FakeRunner's real tools and final-state checks. It is not a production
transcript, runtime isolation evidence or an extraction-quality measurement.
No live model, container, network or private evaluation was used. Task flags and
PROGRESS remain unchanged.

## Second-review repair handoff

Recovery checks read the authenticated tenant ledger across tasks under the
existing tenant tools lock. Another task cannot reuse an affected computer after
unverified cleanup, incomplete lead accounting, or an unended extraction attempt.
Another tenant's events are neither read nor included in this recovery decision.

An extraction attempt ends only after each launched document positively confirms
native accounting and destruction. Calling creation/start and losing its handle
leaves the original reservation active. A method exception is not a cleanup
receipt and unknown spend is not recorded as zero. If the recovery-marker write
fails, the already-durable, unended reservation remains the barrier. Lead starts
without returned handles also remain active; incomplete lead meter totals retain
unused token commitments. Known extraction pre-start failures can release their reservation only after
the known box's destruction succeeds.

Lead and extraction cleanup use the same bounded acknowledgement operation.
Cancellation suppression cannot extend the five-second acknowledgement window;
late adapter results cannot clear a durable recovery requirement. The trusted
adapter still owns actual descendant termination and independent reconciliation.

Lead reservation, tools, extraction, and cached publication use one task deadline
calculation over all segment starts and extraction starts. Publication checks it
again after gates. Authenticated documents must be fresh before preflight and in
the publication transaction, including after gates; their supplied source record
must still match the extracted snapshot. Canonical document-to-fact and
fact-to-batch graph edges propagate document invalidation to downstream outputs.
The existing anchor/value syntax, incremental metering, shared reservations,
original known_at values on resume, and staged all-or-nothing gates are preserved.

Additive regressions live in `tests/extraction/test_quarantine_repair3.py` and
`tests/runner/test_codex_repair3.py`. The original tests/assertions are unchanged.
The final handoff reports focused tests, the exact T035 verifier, and Ruff/strict
mypy results. All verification uses public synthetic inputs and offline adapters.
The lead runtime requires OpenAI when claiming isolated runtime evidence; existing
synthetic provider placeholders remain usable solely for offline fixture coverage.
No configured user model ID was changed.

The coordinator reported unrestricted make check on the preceding source:
1261 passed, 3 approved skips, 15 integration tests deselected. This restricted
worktree did not rerun make check; the coordinator must rerun it after these edits.
T035 remains false. No Git write, acceptance flag, PROGRESS, owner-guard edit,
private eval, network call, or live model call was performed.

Offline verification on the preceding second-review source:

- Extraction: **181 passed, 1 existing approved skip**.
- Runner: **104 passed**.
- Exact task verifier, `uv run pytest tests/extraction -q && uv run python scripts/check_task.py T035`: **exit 0**, **111 acceptance tests passed**, AC1–AC4 passed.
- Ruff check/format: passed, 189 Python files formatted.
- Strict mypy: passed, 123 source files.
- Eighteen additive regression cases pass. The original seven reported failure
  categories were reproduced red before implementation; additional shared-meter
  and unknown-lead-start failures were also reproduced red.

| Regression name | Passing cases |
| --- | ---: |
| `test_t035_ac1_recovery_barrier_covers_other_task_same_tenant` | 3 |
| `test_t035_ac1_unknown_launch_outcome_retains_reservation` | 2 |
| `test_t035_ac1_marker_write_failure_cannot_release_reservation` | 1 |
| `test_t035_ac3_all_publication_paths_share_codex_deadline` | 3 |
| `test_t035_ac2_document_staleness_bound_through_publication` | 4 |
| `test_t035_ac2_document_invalidation_reaches_facts_and_dependents` | 1 |
| `test_t035_ac1_lead_isolated_runtime_rejects_non_openai_provider` | 1 |
| `test_t035_ac1_lead_cancellation_suppression_is_bounded` | 1 |
| `test_t035_ac1_lead_unknown_start_keeps_durable_reservation` | 1 |
| `test_t035_ac1_incomplete_lead_meter_keeps_token_commitment` | 1 |

## Final-review blocker repair handoff

Extraction provider observations and durable token charges are independent.
Cleanup reads charges for the authenticated task, extraction attempt and box
inside the canonical transaction, adds only the native receipt's missing charge,
and reads the resulting ledger total back before accepting reconciliation.
An observed append that committed but lost its acknowledgement is already charged;
it is not charged again. A rolled-back append is reconciled from the native meter.
Receipt mismatches, excess canonical charges, persistence failures and ambiguous
reconciliation acknowledgements keep the attempt unended and its reservation
active. Destruction still runs on these failures.

The analogous lead Normalizer/persist/cancellation seam was reachable and had the
same defect. Lead reconciliation now reads canonical segment usage under the
authenticated tools transaction and marks usage complete only after that
transaction succeeds. Task, release, box and segment identify lead charges and
ends. Missing or mismatched accounting retains the lead token commitment.
No-charge reconciliation allocates no event origin, preserving contiguous
recorder origins and the existing FakeRunner checks.

Extraction checks tenant-wide unresolved lead lifetime ownership before reserving
or launching a box. A runner-emitted start carries runtime evidence and remains
pending without its matching complete end, including when both the start handle
and recovery-marker write are lost. Another task, box, segment or release's end
cannot close it. Other tenants remain isolated. Bare offline budget fixtures
without runtime evidence retain their prior semantics; they do not claim native
execution. No trusted concurrent lead/extraction phase contract is implemented:
an outstanding native lead lifetime blocks extraction.

New additive tests are `tests/extraction/test_quarantine_final_review.py` and
`tests/runner/test_codex_final_review.py`. The initial 21-case run reproduced
component undercharges, the corresponding lead undercharge, accepted excess
charges and unmatched/unended lead ownership before source edits. Eight further
cases expand pending native/synthetic lifetime and fixture coverage. All 29
additive cases pass. Existing assertions, earlier repairs, task flags, PROGRESS
and protected files were left untouched. No Git operations were performed.
New probes use OpenAI provider
configuration and offline synthetic data/adapters only.

Current offline source verification:

- Extraction: **205 passed, 1 existing approved skip**.
- Runner: **109 passed**.
- Exact T035 verifier,
  `uv run pytest tests/extraction -q && uv run python scripts/check_task.py T035`:
  **exit 0**, **140 acceptance tests passed**, **1186 deselected**, AC1–AC4 passed.
  Each pytest invocation used a unique `--basetemp`; the acceptance checker
  creates its own unique temporary directory.
- Ruff check and format: passed, **191 Python files** formatted.
- Strict mypy: passed, **123 source files**.

The coordinator owns full `make check`. T035 remains **false**. Native
containment, authentication/config inventory, immutable mounts and model-only
egress, preventive hard caps over every internal call, descendant termination,
and a trusted native recovery/reconciliation implementation remain prerequisites.
Synthetic SQLite fault injection does not prove PostgreSQL concurrency or real
storage-outage behavior. Extraction quality and general intake remain unproved.
There were no network calls, live models, private evals or production transcripts.
