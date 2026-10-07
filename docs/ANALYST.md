# Agent-first analyst

## Status

Working brain contracts and an advisory investigation controller are implemented.
These are not accepted operational-analyst or certified-runtime evidence. No T030,
T033, T039 or T040 acceptance is claimed, and no feature flag is promoted by this work.
ADR-0002 supersedes the infrastructure-first sequencing, not security/evaluation bars.

## Character and responsibility

One skeptical, commercially practical lead owns the investment thesis and recommendation.
It plans the investigation, chooses relevant tools and skills, seeks disconfirming
evidence, prioritizes material questions and revises when evidence changes.
Proceed, hold and pass are all valid outcomes; proceed is not approval to close.
The lead is neither a coding agent nor a replacement for appraisers, engineers,
environmental professionals, counsel or the owner's investment committee.

```text
Authenticated host request + permitted typed evidence
                      |
                 Lead analyst
          plan -> investigate -> reassess
             /         |          \
  quarantined       public       deterministic finance,
  extraction        research     state, rules and Excel
             \         |          /
             candidate recommendation
                      |
              Independent reviewer
                      |
             evidence-backed revision
                      |
                  reviewed draft
                      |
        existing host composition + all required gates
                      |
             finalize_deliverable only
```

Underwriting and diligence are reusable capabilities, not mandatory extra opinion
agents. Classifier and reflection have narrowly bounded support contracts; the
investigation does not call them merely because a role exists.

## Brain assets

`brain/prompts` defines the lead, extraction, research, verifier, classifier and
reflection contracts. `brain/skills` contains SCREEN, multifamily reconciliation,
underwriting, diligence, research and independent review. `brain/playbook/global.md`
contains original public-reference-informed methods, never customer/firm facts.
The old scaffold acceptance test requires the word `Placeholder`; the retained status
line explicitly says the original placeholder was replaced and behavior acceptance
is pending. No existing test or acceptance bar was changed.

`load_brain` reads only explicit trusted assets without following symlinks, rejects
unreplaced scaffolds, bounds the bundle, freezes asset mappings and fingerprints the
entire release. `cre analyst instructions --brain-root /absolute/path/to/brain
--role lead` exports the instructions, output schema and digest without model calls.
The existing instruction exporter also includes the public playbook when installed.

## Model-directed controller

`AnalystLoop` requires a plan before acting, then lets the lead select its next action:
replan, propose a canonical tool call, request a bounded specialist, draft a question,
or propose a recommendation. Tools execute through the same authenticated ToolRegistry;
there is no model-created state/provenance authority or arithmetic layer.

Every proposed recommendation receives an independent review. Major/stopping findings
require revision; an accepted advisory review never produces a gate PASS. Revisions
need a change log and are reviewed again. The host bounds steps, review attempts and
elapsed time. Source pins are resolved against the existing current scoped ledger;
forged/stale pins and stale turn responses refuse. Scope changes during await refuse.

If a question has no supportable default, QuestionDraft preserves the missing evidence
and decision consequence without inventing an Assumption. Blocking questions stop;
unanswered material questions cannot support proceed. The authenticated persistent
host must still persist/answer questions, invalidate affected versions and start a
new evidence-bound investigation; this controller is not that service.

Specialists receive only host-authorized snapshots. Extraction is unavailable without
that host seam. Research uses the canonical provider, cannot invent cited source IDs,
and cannot promote public guidance into property Fact pins. The verifier is advisory
and receives the evidence/candidate, not write tools.

Outcomes are `reviewed_draft`, `needs_user`, `review_blocked` or `step_limit`.
All carry `publication=not_authorized`. The controller cannot call finalize_deliverable,
draft_external or send_external. Checked SCREEN/workbook composition and publication
remain separate existing host responsibilities, not a free-text model memo.

## Cited knowledge

The single rights-reviewed catalog and KnowledgeLibrary remain authoritative.
Host-injected knowledge_search uses SearchRequest and SearchResult, existing tool
budgets/idempotency and the same CLI/MCP registry. It performs no download and writes
no property facts. Without a provider it is not advertised.

Every hit retains edition, source URL, page/section when actually available, hash/
retrieval metadata, applicability, caveats, `global_public` and
`public_reference_not_deal_fact`. `reference_only` is bibliography, not a read passage;
`not_cached` is an explicit body-access limitation. Copyrighted books/standards are not
ingested. Operator opt-in imports remain outside Git/tenant/evaluation storage.

The source-research synthesis informed the thesis, reconciliation, repayment/collateral,
downside, specialist-escalation and review procedures. It is public knowledge research,
not transaction-quality evidence. An unavailable cached source must not be represented
as read or current.

## Devin development path

`DevinDraftClient` implements the documented v3 session create/get/terminate endpoints:

- Explicit Outpost pool and pinned security profile; no cloud/default fallback.
- Normal Devin mode, repo-less request, no selected knowledge/secrets/attachments,
  no approval bypass and disposable sessions.
- Required structured outputs, scoped turn identities, per-session ACU request limits,
  bounded polling/deadlines and host-provided durable intent/session/cleanup receipts.
- No blind retry after uncertain creation or interrupted state. Host reconciliation
  is required, rather than duplicating billed work or assuming termination.
- Known sessions are terminated before returning; unexpected descendants or ambiguous
  cleanup block the journal. ACUs are provider-reported, not a token-cancellation receipt.

It is intentionally **not** a certified Runner. Requesting an Outpost pool does not
independently prove placement. Repo/secret selection and a profile binding do not prove
full filesystem/tenant containment. ACU limits do not prove preventive token caps.
Exited parent status does not prove descendant containment. Production attach/resume,
kill/restart recovery and canonical token accounting remain unverified.

`cre record --advisory-probe` accepts only an installed trusted host factory and public
synthetic evidence; it defaults to refusal without that factory. Captures are new,
exclusive, outside Git and not under `transcripts/`. They contain a hashed result and
manifest bound to the host ledger, labelled `unverified_public_development`, not
production runtime acceptance. Ordinary `cre record` keeps its existing requirements.
There is no environment/deal-file plugin that can install a host.

Live application verification requires a scoped service-user Devin credential plus
an authorized Outpost/security-profile binding. Attach-profile permission is required
by the API; do not weaken organization/enterprise floors or choose an opt-out. The key
stays in the authenticated host and is never placed in analyst instructions or sessions.

## Remaining acceptance work

- Genuine public synthetic cases: plan, extraction, cited research, canonical finance/
  Excel tools, material question, independent objection, revision and checked outputs.
- A new evidence/user correction that reopens the thesis and invalidates old versions.
- Prompt-injection, scope/isolation and interruption/restart evidence from actual runs.
- Independent investment-quality scoring, with private truth inaccessible to analyst/
  builder and no fabricated transcripts or model calls in unit tests/CI.
- Certified runtime and persistent application host, then existing publication gates.
- Permitted Git promotion after required CI and protected/owner gates. Hosted-CI scope
  remains an owner decision; no workflow is disabled or rewritten to avoid that decision.

Offline tests establish schema, tool/controller and HTTP plumbing only. A research
synthesis, finished prompt bundle or passing test count is not completion evidence.

## API sources

- https://docs.devin.ai/api-reference/v3/sessions/post-organizations-sessions
- https://docs.devin.ai/api-reference/v3/sessions/get-organizations-sessions
- https://docs.devin.ai/api-reference/v3/sessions/delete-organizations-sessions
- https://docs.devin.ai/product-guides/security-profiles
