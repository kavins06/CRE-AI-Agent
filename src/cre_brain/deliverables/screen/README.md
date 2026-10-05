# T038 SCREEN source handoff

This is deterministic source plumbing on reviewed T033 `22d4dc7`, not extraction,
runtime acceptance, calibrated risk or operational analyst quality.

Host composition:

1. Wrap the existing authenticated T032 input provider in `ScreenInputs` before
   constructing `ToolRegistry`. Provide its typed `risk_policy` explicitly.
2. Construct the real `GateService` with the existing `TrustedInputs`, same tenant
   scope and canonical SQL engine. Construct `ScreenService(registry, authority,
   buy_box)` with the host's existing typed buy-box policy.
3. Host intake must independently authenticate the document IDs and filenames,
   then pin each `Document` with `ScreenInputs.register_document(context, document)`.
   This host-only method is not an analyst tool. Ingest host-issued anchored facts
   through `facts_put`. Call `run` with those registered descriptors, current
   `Reference` pins and a new run identity. Unregistered or changed descriptors
   refuse before headline composition. The repository does not yet implement real
   authenticated document intake; synthetic fixture registrations prove this seam
   only. Hosts must restore the same pins on resume, rather than register descriptors
   from an untrusted run request.
4. Release each returned artifact ID only through `finalize_deliverable`. The
   service registers drafts, source edges and authenticated authority bindings;
   it cannot grant PASS or a final state itself.

Decisions:

- Classification uses explicit filename rules over independently host-pinned
  document metadata. Pins include tenant, task, deal and brain release; a document
  ID cannot be rebound to another filename in that context. Ambiguous, unknown
  and unsupported authenticated inputs produce scoped canonical questions;
  no classifier/model fallback or authenticated raw intake is claimed here.
- Headline facts retain their canonical claim and usable source anchors: a page
  or a nonblank sheet and cell. SCREEN and the independent coverage gate share
  that location rule. Seller claims remain SELLER_ASSERTION.
  Reference/interpretation facts cannot supply headlines or risk.
- Risk is a weighted index of occupancy and DSCR threshold breaches. Thresholds,
  weights, policy identity/version and provenance are required host configuration;
  weights sum exactly to one. It is not a default underwriting assumption or a
  calibrated probability. Stored facts, immutable policy input, finance code hash,
  dependencies and a typed recipe allow the real gates to reproduce the result.
- The minimal JSON schema is `{"markdown": "<the identical memo>"}`. All memo
  numerical occurrences have host-issued Fact/Calc citations and units. Both files
  are captured once with authenticated byte identities and companion hashes.
  Every gate consumes that immutable pair, including the numeric gate; it never
  rereads the live companion. A final workspace recheck still refuses observed
  mutations. Publication atomically stores both validated byte strings with a
  bounded authenticated header in the protected SQL publication column of the
  final canonical version. Whole-row append-only guards protect these bytes.
  Ordinary release events contain only bounded publication IDs, paths and digest
  references; bodies and reversible whole-body encodings stay out of events.
  Workspace paths remain mutable mirrors. Host download/delivery consumers use
  `ToolRegistry.published_artifact` with authenticated context to retrieve exact
  protected bytes. An omitted version requires current canonical freshness;
  an explicit version permits an authenticated archival read after invalidation.
  This does not claim OS immutability of workspace files.
- Missing substantive data or risk configuration stays unknown and blocks release.
  Questions use `unknown; no default`; no financial Assumption or zero is invented.
  Period-bearing headline facts are refused because this minimal schema cannot
  cite standalone canonical date facts for their displayed periods.
- Artifact identities separate tenant, task, deal, release and run. New runs get
  exclusive versioned files; existing canonical edges invalidate prior outputs
  when fact versions change. Monotonic nanoseconds measure source composition to
  draft registration per admitted run, including failures; finalization time is
  outside that measurement. This is not an evaluation of the latency target.
- FakeRunner rechecks the authenticated draft identity and immutable snapshot
  after confirming final canonical state, then requires a trusted release event.
  This allows the real T037 authority to validate replay without accepting a
  caller's final metadata or gate verdict. Companion integrity is rechecked too.
  Finalization (including cached replies), FakeRunner replay and external sending
  use one trusted-release check: complete blocking gate results, matching canonical
  parent/version, tool source, tools runner, current release ID, both hashes and
  the exact published bytes. Legacy releases without immutable publication fail
  closed and must be regenerated; no unsafe compatibility fallback is provided.

Validation and remaining acceptance:

- Additive AC tests first failed for missing SCREEN. Period/date and annual-rent
  display tests also failed before their fixes.
- Focused SCREEN suite: 58 passed, including public generator documents/canonical
  fixture facts and synthetic provider recording produced by `record_segment`,
  then FakeRunner replay through real tools/gates. Recordings live only in pytest
  temporary directories, carry `synthetic_plumbing_only`, and prove no quality.
- Ruff check/format and strict mypy pass. `uv run python scripts/check_task.py
  T038` exits zero: AC1, AC2 and AC3 PASSED, 58 tests passed without skips.
- The one constrained `make check` run passed lint/types and recorded 1,169 tests
  passed, 55 failed, 2 errors, 3 approved skips and 15 integration deselections.
  Failures are outside SCREEN/runner/finance/gates: the read-only `/tmp/.git`
  ancestor makes existing knowledge cache security checks reject temporary caches;
  Git write fixtures are prohibited; offline bootstrap/wheel packages (including
  hatchling and idna) are absent from the writable uv cache. Inherited basetemp
  also broke nested pytest checks in that run. Correcting the temporary command
  guard/pytest harness and rerunning only knowledge/guard areas restored those
  nested checks: 41 passed, with 40 knowledge failures and 5 prohibited-Git-write
  failures remaining. No security gate, assertion or test was weakened.
- Raw local verification logs: `/tmp/t038-task-check.log`,
  `/tmp/t038-make-check.log`, `/tmp/t038-harness-corrected.log`.
- T035 extraction and authenticated isolated runtime/dependency acceptance remain
  unaccepted; T038 stays false. Durable host artifact/recipe authority must be
  restored by the host on resume; this source uses the existing trusted binding
  seams, not a new persisted state store.
- Gate implementation files are protected paths and require the existing owner
  review/protected-change process on promotion. Owner guard files, existing tests,
  feature flags, PROGRESS, Git history and publishing are unchanged.

Repair regression evidence (2026-10-05):

- The additive regressions first reproduced blank anchors at both boundaries,
  companion A-B-A mutation in both primary directions, missing immutable publication,
  swapped/unregistered descriptors, and forged external sends. A further red-first
  test reproduced cached-finalization release-authentication bypass.
- The focused SCREEN suite and exact T038 verifier pass with 81 non-skipped tests.
  Existing assertions and AC definitions remain intact. Ruff check/format and strict
  mypy pass. These are synthetic source/plumbing checks only; T038 stays false.
- Publications are durable in the protected append-only SQL column, while document,
  artifact and recipe authority pins still need host restoration on resume. Real
  document intake and integration of the protected retrieval adapter into host
  download consumers remain host work; source tests do not establish runtime or
  analyst quality.

- The single repair `make check` used unique basetemp and TMPDIR beneath
  `/srv/infra/devin-outpost/sessions/devin-70d6ca47bdbf4faf8083ca76c4988784/home/test-temp/t038-repair-check-un96hjcv/`,
  outside the worktree, with offline dependencies and executable guards against
  Git and live runner operations. Lint, format and strict types passed; unit results
  were 1,199 passed, 48 failed, 2 errors, 3 approved skips and 15 integration
  deselections. All SCREEN, runner, finance and gate tests passed. The failures
  were 40 knowledge-cache tests (the sandbox mounts read-only `.git` markers at
  every writable external root), 7 Git-dependent tests denied by the user constraint,
  and one offline bootstrap test; two wheel-test errors lacked cached hatchling.
  An attempted isolated temporary mount failed with `Operation not permitted`.
  No security check, existing assertion or acceptance criterion was weakened to
  hide these constraints. The original adjacent gate sanitization assertion caught
  a capture-adapter regression and passed after the provider error was correctly
  classified as `authority_unavailable`.
- Repair logs: `/tmp/t038-repair-red.log`, `/tmp/t038-repair-send-red2.log`,
  `/tmp/t038-repair-cache-red.log`, `/tmp/t038-repair-focused.log`,
  `/tmp/t038-repair-verifier.log`, `/tmp/t038-repair-make-check.log`.
