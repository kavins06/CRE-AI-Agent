---
name: screen
description: Consume the host deterministic SCREEN path and resolve its scoped evidence questions.
---

# Screen for a decision, not a favorable score

Identify the request, owner policy and evidence needed to support the initial thesis.
Rank the first investigations by decision consequence. Use SCREEN to decide whether
further underwriting is justified, whether evidence is missing, or why the thesis
should be passed on; it does not prove a purchase is attractive.

Use canonical host-issued Fact pins only. The host classifies document metadata
with rules first. Unsupported, unknown or ambiguous documents require a scoped
question; this source implementation does not call a classifier model.

Facts from seller documents retain SELLER_ASSERTION until separately verified.
General library references are reference material, never property facts. Read
facts through facts_get; never read raw seller files or invent an extraction API.

The host composes its typed buy-box and bounded versioned risk policy. risk_score
is an exact deterministic CalcResult with stored input pins, policy provenance and
code version. It is an uncalibrated threshold breach index, not an outcome forecast.
An eligible buy-box decision neither verifies seller claims nor grants gate PASS.

Unknowns stay unknown. Answer scoped questions with evidence; never insert zeros
or default financial assumptions. Rebuild stale outputs as a new immutable version.
The Markdown and JSON memo carry identical content and checked byte identities.
Only finalize_deliverable can release either artifact through every required gate.
External sends are outside SCREEN scope. Synthetic recordings and FakeRunner replay
prove tool and gate plumbing only; they provide no operational quality evidence.

State the strongest contrary case. Separate commercial interpretation from deterministic
buy-box/risk output. Recommend hold if evidence essential to the decision is unavailable,
or pass when available evidence defeats the thesis/policy. Identify what could change
the recommendation; do not invent universal thresholds or probabilities.

Before a recommendation is considered reviewed, an independent verifier challenges
the evidence, thesis and unresolved gaps. Revise using closure evidence, not a more
confident narrative. Reviewed drafts are not finalized deliverables.
