# LEARNING: how the brain improves itself

> The product is an autonomous CRE acquisition analyst, "the Devin of real estate". This document specifies its self-improvement loop.

The loop follows Andrej Karpathy's autoresearch pattern: propose a change, run a bounded experiment, measure it, then keep or revert. It is adapted in five ways so that it doesn't fool itself.

## 1. What may change and what may not

| Surface | Learning loop may edit? |
|---|---|
| `brain/skills/**`, `brain/prompts/**` (incl. overlays), `brain/playbook/global.md` | **Yes**. These are the "weights" |
| Firm playbooks | Only in firm-scoped runs; never promoted to global without sanitization (M7) |
| `src/cre_brain/**` tool code | Candidate branches only, through a normal PR with full tests |
| Everything in `scripts/protected_paths.txt` (evals, gates, policy, `keep_rule.py`, `program.md`, `gates.yaml`, `budget.yaml`) | **Never** |

## 2. Runner for training (v1)
- Every candidate is evaluated by running **Codex CLI analyst sessions** (`CodexRunner`) in **repo-less containers** on the frozen dev fixtures. No separate model API keys are needed.
- The scorer runs afterwards as a separate process.
- **Auth:** the owner's Codex login, used by **one serialized job stream** (`codex_login_max_concurrency: 1`), on public and synthetic data only. Parallel or customer-data runs require API-key auth (SPEC §9).
- When SDK runners are added (M8), the accepted brain is re-validated on them, and per-runner overlays are tuned there.

## 3. The loop (`learning/runner.py`, configured by [program.md](../program.md))
```
pick target deliverable kind K (largest gap to its bar, rotated)
load frozen dev fixtures for K (8–10 deal states checkpointed just before K)
baseline = evaluate(current brain, K, dev, k=3)                 # cached per release
repeat until nightly caps reached:
    candidate = GEPA proposer -> ONE edit to ONE artifact for K (from failure categories)
    commit on autoresearch/<tag>
    score = evaluate(candidate, K, dev, k=3)                    # paired with baseline, same fixtures
    if keep_rule.dev_pass(score, baseline):
        verdict = scoring_service.confirm(candidate_release, K) # selection holdout, private; returns pass/fail + aggregates
        keep if verdict.pass else revert
    else revert
    append row to results.tsv
open PR autoresearch/<tag> -> dev (never auto-merge)
```
**Per-experiment cost:** about 30 dev sessions (10 fixtures × k=3) plus the holdout confirmation. Each experiment is allowed **up to 3 h of wall-clock time**. With the default caps (`nightly_sessions: 200`, `nightly_wallclock_h: 10`), a night runs about **3–5 experiments**. That is deliberate: a few well-measured experiments beat many noisy ones.

## 4. GEPA as a proposer (`learning/gepa_proposer.py`)
- **No DSPy.** It requires LiteLLM, which is banned. Use the `gepa` package directly.
- Give GEPA a **custom language-model callable that wraps `codex exec -p reflector`**, so no LiteLLM default is ever used [verify the GEPA LM-callable interface in T071].
- **Use GEPA only to propose one candidate edit per experiment.** Its internal Pareto acceptance is not used; `keep_rule` decides. Configure the smallest proposal budget, for example a single reflective mutation per call [verify the config name].
- The proposer sees only **failure categories** (for example `checksum_tie_failed: rent_roll_vs_gpr`), never rubric text or holdout content.

## 5. Keep rule (`learning/keep_rule.py`, protected)
`dev_pass` is true only if **all** of these hold:
1. **Paired improvement.** On the same dev fixtures with k=3, the bootstrap CI of `mean(candidate − baseline)` has its lower bound above 0, at confidence level `1 − α/m`. Here α = 0.05 and m = the number of candidates tried that night (Bonferroni).
2. **Counter-metrics.** None worsens beyond its tolerance in `program.md`: false flags, question rate, tokens, latency, escalation rate.
3. **Simplicity.** On a tie, the shorter artifact wins.

Then the holdout confirmation must show improvement ≥ 0 with no regression on any critical item.

**Required statistical tests (T072), in simulation:**
- **Null false-keep rate.** Two identical brains with seed noise, n = 10 fixtures, k = 3, per-item score SD 0.15. Over 2,000 simulated experiments, the false-keep rate must be **≤ 1%** (binomial 95% upper bound ≤ 1.5%).
- **Power.** A true effect of +0.10 under the same noise must be kept in **≥ 80%** of experiments.
- If both cannot be met at n = 10, the test must report the minimum n that meets them, and `program.md` uses that n.

## 6. ACE playbook queue (M7)
- Live runs only **propose** bullets, written to `learning/queue/`.
- Candidates come only from deterministic signals: gate failures that were later fixed, parity diffs, checksum breaks, owner corrections.
- **Bullet metadata:** scope (deliverable kind, asset class), source run IDs, helpful/harmful counters.
- **Limits:** a cap of 100 per scope, a contradiction check, and incremental deltas only (never a full rewrite).
- **Promotion path:** sanitization (M7) → keep rule on fixtures → merged into `brain/playbook/global.md` via PR.

## 7. Corrections (DAgger)
Owner or user corrections come from two places:
- `POST /corrections`
- uploaded user edits to deliverables (SPEC §4 versioning)

Each correction becomes a `DecisionRecord`:
- state ref
- agent action
- correction
- type (fact / convention / preference / judgment-range)
- scope

That record then becomes:
1. a **private eval case** in the private repo
2. a firm or user memory item
3. a candidate global lesson, for fact and convention types only, after sanitization and the keep rule

## 8. Releases and nightly operation
- **Brain Release:** a manifest hash over `brain/`, firm playbook versions, `config/*.yaml`, the gates code hash, runner and model IDs, and the Codex CLI version. Every task records its release.
- `cre release rollback <id>` reverts to an earlier release.
- Rollback requires the recorded gate code and Codex CLI version; a release built without Codex can be restored offline only when the CLI remains unavailable. It never installs runtime software.
- Release hashes prove content integrity, not owner approval. The offline administrative CLI assumes an operator-controlled checkout and trusted local manifests. Do not import seller, analyst or web-supplied manifests; candidate promotion must pass the evaluator/owner controls before distributing a release. Global brain synchronization to analyst boxes is read-only (§3 of SPEC). Untrusted release import/signing is not implemented by T004.
- `cre learn nightly`:
  1. skips with `SKIPPED_NO_RUNNER` if Codex isn't usable
  2. rotates kinds by gap
  3. respects `nightly_sessions` and `nightly_wallclock_h`
  4. writes a PR plus a PROGRESS entry
- A weekly end-to-end non-inferiority run checks that no deliverable metric drops by more than 2 points.

## 9. Guardrails
- Graders, gates, the keep rule and the holdouts sit outside the editable surface and are protected by path. Holdouts are physically separate (EVALS §1).
- **Synthetic-vs-real transfer:** for each accepted change, compare its delta on synthetic data with its delta on real anchors (C/D, and I later). If the transfer ratio for a kind falls below 0.6, stop optimizing that kind on synthetic data.
- The night's top-scoring outputs are sampled into `learning/review/` for the owner to spot-check.
