# ADR-0001: Ship a SCREEN vertical slice before more orchestration

## Status

Accepted

## Date

2026-10-04

## Context

The project has a strong deterministic foundation: canonical facts and calculations,
provenance, append-only state, finance engines, policy gates, checked SCREEN output,
Excel recalculation/parity, quarantined extraction, and durable job claims. The current
bounded `cre run` candidate composes those pieces for synthetic SCREEN plumbing.

It is not yet an operational autonomous analyst. Genuine Codex execution still lacks
same-session proof for containment, preventive hard caps, descendant termination,
cancellation receipts, killed-run attach/resume, persistence-outage recovery, and
canonical usage reconciliation. The CLI also needs a trusted host installed in-process;
there is no operator-facing submit/status service. T039 and T040 therefore remain false.

The recent repair cycle exposed a recurring pattern. Mutable `ToolRegistry` state crossed
async boundaries; each repair pinned one more consumer, then review found a sibling path
still using the mutable context or engine. The local fixes were necessary, but continuing
to add feature-specific guards would increase code faster than product capability.

Current complexity falls into four categories:

1. **Necessary safety complexity.** Tenant scoping, canonical number provenance,
   deterministic gates, claim revisions, exact publication versions, preventive budgets,
   cleanup evidence, and owner-controlled publication cannot be removed.
2. **CRE domain complexity.** Rent-roll/T-12 normalization, projections, debt, returns,
   waterfalls, scenarios, tax and Excel parity are legitimate deterministic domain work.
3. **Incomplete-integration complexity.** Guarded transports, repeated binding checks,
   retained event loops, synthetic capability proofs, and unavailable recovery paths exist
   because there is not yet one authenticated persistent runtime boundary.
4. **Accidental complexity.** Lifecycle predicates are duplicated, `run.py` has runtime,
   publication, replay and watchdog responsibilities, and an extensive advisory-review
   seam exists without a verifier transport that can use it.

The dominant bottleneck is category 3, not missing finance features or more analyst
roles. Adding revisions, learning, evaluation orchestration, broad underwriting
publication, or another reviewer now would optimize around the bottleneck.

## Decision

The next product milestone is one narrow, genuine, SCREEN-only vertical slice:

```text
authenticated request + source pins
  -> bounded extraction
  -> one lead runtime segment
  -> deterministic SCREEN gates
  -> exact protected publication
  -> durable status/replay
```

Work proceeds in this order:

1. Prove the installed runtime boundary against T030/T033 requirements on the Outpost.
2. Put that boundary behind a persistent host with minimal submit, status and replay
   operations. Do not add more behavior to the retained in-process CLI loop.
3. Run the existing SCREEN path with genuine runtime, cancellation, accounting and
   restart evidence.
4. Only then connect the already-built read-only advisory reviewer and a bounded revision
   cycle.
5. Expand to UW_MODEL publication, broader multi-agent roles, evaluation and learning only
   after the SCREEN slice has measured reliability and quality evidence.

Unsupported paths continue to refuse cleanly. Existing T039/T040 criteria are not changed
or weakened; this is sequencing, not acceptance redefinition.

For the current implementation:

- Keep `ToolState`; it is the canonical transactional authority.
- Keep post-await checks at actual authority boundaries. Immutable snapshots remove
  configuration drift, but they cannot prove that a durable claim, file or external
  process remained live while awaiting I/O.
- Reuse one immutable per-job authorization/ledger snapshot across extraction, runner and
  cleanup instead of adding path-specific context reads.
- Consolidate the duplicated completed-job predicate used by `RunGateService` and
  `RunPublicationAuthority`, while retaining the independent finalization barrier.
- Split publication/replay from runtime/watchdog orchestration when the persistent host is
  introduced; moving code into files before that boundary is known would be churn.
- Keep `ReviewSnapshot`, `ReadLimits` and the advisory service on their isolated task
  branch for now. They are defensible for an untrusted read-only reviewer, but provide no
  product value until authenticated verifier transport and PostgreSQL bounded-read proof
  exist.

## Alternatives considered

### Continue implementing the full specification in task order

Rejected for now. It would add revisions, review, evaluation and learning on top of an
unproven execution boundary. More tests would improve synthetic confidence without making
the analyst runnable.

### Remove the safety layers and build a direct model-to-memo prototype

Rejected. This would erase the project's differentiators and could publish wrong numbers,
cross-tenant state, or unverifiable claims. The deterministic finance and publication
layers are not the overengineering problem.

### Refactor the whole run loop before runtime proof

Rejected. A large rewrite would invalidate reviewed safety behavior and still leave the
same external bottleneck. Only local deduplication is justified before the host boundary
is proven.

### Integrate advisory review immediately

Deferred. The current seam is bounded and read-only, but no authenticated verifier
transport exists. Integrating approximately another subsystem now would increase the
maintenance surface without producing a real second analyst.

## Consequences and stop rules

- Product breadth pauses while runtime evidence is missing.
- The first usable release may produce only SCREEN; that is intentional.
- No task flag changes from synthetic evidence.
- If the installed Codex CLI cannot provide preventive hard caps or authenticated
  cancellation/resume receipts, stop extending its adapter and make the runtime choice an
  explicit owner decision rather than simulating those guarantees in host code.
- The persistent host must replace, not wrap, retained event-loop behavior.
- The advisory branch can be integrated when its transport exists and bounded PostgreSQL
  reads pass; until then it remains reviewed source, not an operational capability.
- Continue only when the next change closes a genuine-runtime acceptance gap or removes
  accidental complexity without weakening tenant, provenance, budget, claim or owner
  gates.
