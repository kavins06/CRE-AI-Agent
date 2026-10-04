# LEARNING: how the brain improves itself

> The product is an autonomous CRE acquisition analyst, "the Devin of real estate". This document specifies its self-improvement loop.

The loop follows Andrej Karpathy's autoresearch pattern: propose a change, run a bounded experiment, measure it, then keep or revert. It is adapted in four ways so it does not fool itself.

## 1. What may change and what may not

| Surface | Learning loop may edit? | Notes |
|---|---|---|
| `brain/skills/**`, `brain/prompts/**`, `brain/playbook/global.md` | **Yes** | These are the "weights" |
| Firm playbooks | Only via firm-scoped runs | Never promoted to global without sanitization |
| `src/cre_brain/**` tool code | Candidate branches only | Must pass the full test suite and a human-reviewed PR |
| `evals/**`, `src/cre_brain/gates/**`, `tests/protected/**`, `config/gates.yaml`, `program.md` | **Never** | Protected by hash check, CODEOWNERS and CI |

The optimizer process runs with read-only access to the evaluator, and it never sees the holdout data or rubric text.

## 2. The loop (`learning/runner.py`, configured by [program.md](../program.md))

```
pick target deliverable kind K (worst metric vs. its bar, rotated)
load frozen fixtures for K  (deal states checkpointed just before K is produced)
baseline = evaluate(current brain, K, dev split, k=3)
repeat until budget exhausted:
    candidate = GEPA.propose(artifact for K, failure categories from last eval)
    git commit on autoresearch/<tag>
    score = evaluate(candidate, K, dev split, k=3)        # paired with baseline, same seeds
    if keep_rule(score, baseline): confirm on selection holdout
         if confirmed: keep (branch advances), baseline = score
         else: revert
    else: revert
    append row to results.tsv
open PR "autoresearch/<tag>: <K> +x.x" with results.tsv summary  (never auto-merge)
```

**Why one deliverable at a time on frozen fixtures:** running the full pipeline for every experiment costs too much and is too noisy. Fixtures make each experiment cheap (cents to a few dollars) and attributable.

## 3. Keep rule (`learning/keep_rule.py`)

A candidate is kept only if **all** of the following hold:
1. **Paired improvement.** On the same dev items and seeds with k=3 repeats, the bootstrap 95% CI of `mean(candidate - baseline)` has a lower bound above 0.
2. **Multiple comparisons.** The CI level is Bonferroni-adjusted for the number of candidates tried that night.
3. **Confirmation.** On the selection holdout (not the sealed test), the improvement is ≥ 0, and no critical item regresses.
4. **Counter-metrics.** None of the following worsens beyond its tolerance in `program.md`:
   - false-flag rate
   - question rate
   - cost per task
   - latency
   - escalation rate
5. **Simplicity.** When scores tie, the shorter artifact wins.

The rule's unit tests must show it **rejects pure noise**: two identical brains with random seed variation must never be kept, across 200 simulated nights.

## 4. GEPA adapter (`learning/gepa_adapters.py`)
- Uses `gepa.optimize_anything`, with one adapter per deliverable kind. The seed candidate is the current artifact text.
- The evaluator returns a score plus **failure categories only**, for example `checksum_tie_failed: rent_roll_vs_gpr` or `provenance_missing: 3 numbers`. It never returns rubric text or holdout content.
- The reflection model is the `reflection` role from config.
- The budget is `max_metric_calls` from `program.md`.

## 5. ACE playbook (`memory/ace_queue.py`)
- **Live runs only propose bullets.** They write to `learning/queue/`. They never edit `brain/playbook/global.md` directly.
- Candidates come only from deterministic signals: gate failures that were later fixed, parity diffs, checksum breaks, user corrections. The agent's own opinion of its work is not a source.
- Each bullet records:
  - its scope (deliverable kind, asset class)
  - the run IDs it came from
  - helpful and harmful counters
- At most 100 bullets per scope. A contradiction check runs, and bullets are incremental deltas only (never full rewrites).
- **Promotion:** sanitization gate → keep rule on fixtures → merged into `brain/playbook/global.md`.

## 6. DAgger corrections (`control/corrections.py`)
- When a user corrects the agent (a number, an assumption, a judgment, a memo edit), a `DecisionRecord` is stored with these fields:
  - `state_ref`: the deal state at that point
  - `agent_action`
  - `correction`
  - `correction_type`: fact / convention / preference / judgment-range
  - `scope`
- Each record becomes:
  1. a **private eval case** for that user or firm
  2. a **firm or user memory** item
  3. a **candidate global lesson**, only if `correction_type` is fact or convention, sanitization passes, and the keep rule passes

## 7. Releases (`release/`)
- A **Brain Release** is a manifest hash over `brain/`, firm-playbook versions, `config/*.yaml`, `src/cre_brain/gates`, and the model IDs.
- Every task records the release it ran on, so it can be replayed.
- `cre release rollback <id>` restores the prior release.
- Every accepted change is re-run weekly in an end-to-end non-inferiority check: no deliverable metric may drop by more than 2 points.

## 8. Nightly operation (`learning/nightly.py`)
1. Stop immediately with `SKIPPED_NO_KEY` if `config.live_enabled("lead")` is false.
2. Read the budget from `config/budget.yaml` (`nightly_usd`, default 25). Stop cleanly when the cumulative spend reaches the cap.
3. Rotate target deliverable kinds by largest gap to their bar.
4. Write the experiment PR and a summary to `PROGRESS.md`.

## 9. Guardrails against the loop fooling itself
- Graders, gates and holdouts are outside the editable surface and are hash-checked in CI.
- The sealed test runs only in CI, once per release, and each run is logged.
- Synthetic vs. real transfer is tracked: for each accepted change, record its delta on synthetic sets and on real-anchor sets (CMBS gold pairs, and owner deals once available). If the transfer ratio for a deliverable kind falls below 0.6, stop optimizing that kind on synthetic data.
- The top-scoring outputs of each night are sampled into `learning/review/` for human spot checks. Reward hacking shows up there first.
